"""
Export officer-confirmed/denied alert feedback into a retraining-ready file.

FR10 ("accept confirmation or denial of events from recipients and store these
responses for future retraining") is implemented in two halves:
  1. Storage — `POST /api/sms/telerivet-callback` -> `services.sms.handle_inbound()`
     already writes `feedback` ("CONFIRMED"/"DENIED") onto the matching
     `alert_records` doc. This half is live and verified.
  2. Retraining — nothing in ml/ previously consumed that feedback at all. This
     script closes that gap by joining feedback back to the feature vector the
     model actually scored at alert time (`predictions.features`, stored per
     prediction) and writing a labeled, retraining-ready file.

This is a deliberately human-in-the-loop export, not an automatic retrain:
  - A CONFIRMED reply is reasonable positive-label evidence — the officer is
    asserting the conditions described in the alert matched what they observed.
  - A DENIED reply is weaker evidence for a negative label. It only means the
    officer did not confirm — not that a landslide was independently verified
    absent. Treating every DENIED as ground-truth label=0 risks teaching the
    model to distrust its own true positives whenever an officer is unsure,
    slow to reply, or simply wrong. Review DENIED rows before merging them into
    training_matrix.parquet.

Usage:
    python scripts/export_feedback_for_retraining.py
    -> writes data/processed/officer_feedback_retraining.parquet
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pandas as pd
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "slope_angle", "aspect", "twi", "drainage_density",
    "ndvi", "soil_class", "landuse_class",
    "daily_mm", "antecedent_3day_mm", "antecedent_5day_mm",
    "antecedent_10day_mm", "rainfall_intensity_ratio",
]


def _resolve_prediction(db, alert: dict) -> dict | None:
    """
    Find the predictions doc this alert was based on.

    alert["prediction_id"] is usually a stringified predictions._id, but the
    manual/expert-override path (POST /api/predict/alert) writes the literal
    string "manual" instead of a real id (backend/app/routes/predict.py:459) —
    so a direct _id lookup won't always work. Fall back to the most recent
    prediction for that slope unit on the alert's sent date.
    """
    pid = alert.get("prediction_id")
    if pid and pid != "manual":
        try:
            doc = db.predictions.find_one({"_id": ObjectId(pid)})
            if doc:
                return doc
        except Exception:
            pass  # not a valid ObjectId — fall through to the date-based lookup

    unit_id = alert.get("slope_unit_id")
    sent_at = alert.get("sent_at")
    if unit_id is None or sent_at is None:
        return None
    sent_date = sent_at.date().isoformat() if hasattr(sent_at, "date") else str(sent_at)[:10]
    return db.predictions.find_one({"slope_unit_id": unit_id, "date": sent_date})


def main():
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "landslide_ews")
    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    db = client[db_name]

    feedback_alerts = list(db.alert_records.find({"feedback": {"$ne": None}}))
    logger.info("Found %d alert_records with officer feedback", len(feedback_alerts))

    rows = []
    skipped = []
    for alert in feedback_alerts:
        pred = _resolve_prediction(db, alert)
        if pred is None or not pred.get("features"):
            skipped.append({
                "alert_id": alert.get("alert_id"),
                "slope_unit_id": alert.get("slope_unit_id"),
                "reason": "no matching prediction with stored features",
            })
            continue

        features = pred["features"]
        row = {c: features.get(c) for c in FEATURE_COLS}
        row.update({
            "unit_id": pred.get("slope_unit_id"),
            "date": pred.get("date"),
            "district": alert.get("district"),
            "label": 1 if alert["feedback"] == "CONFIRMED" else 0,
            "feedback": alert["feedback"],
            "feedback_confidence": "officer_reported",  # not independently verified ground truth
            "risk_probability_at_alert": alert.get("risk_probability"),
            "alert_id": alert.get("alert_id"),
            "feedback_at": str(alert.get("feedback_at")),
            "source": "officer_feedback",
        })
        rows.append(row)

    if skipped:
        logger.warning(
            "Skipped %d feedback record(s) with no matching prediction/features: %s",
            len(skipped), skipped,
        )

    out_path = ROOT / "data" / "processed" / "officer_feedback_retraining.parquet"
    if not rows:
        logger.warning("No usable feedback rows found — nothing written.")
        client.close()
        return

    df = pd.DataFrame(rows)
    df.to_parquet(out_path, index=False)

    n_confirmed = (df["feedback"] == "CONFIRMED").sum()
    n_denied = (df["feedback"] == "DENIED").sum()
    logger.info(
        "Wrote %d rows (%d CONFIRMED, %d DENIED) -> %s",
        len(df), n_confirmed, n_denied, out_path,
    )
    logger.info(
        "This file is NOT auto-merged into training_matrix.parquet. Review DENIED "
        "rows before including them as negative labels — see this script's docstring."
    )
    client.close()


if __name__ == "__main__":
    main()
