"""
Run the XGBoost model (ImbPipeline: imputer -> SMOTE -> XGBClassifier) over all 396 slope units using rainfall values from the
May 2023 Northern Province landslide event (CHIRPS-verified figures) and save
as today's predictions in MongoDB so the risk map shows a high-risk scenario.

Real model + real terrain features + historically-accurate rainfall inputs.

Usage:
    python scripts/replay_historical.py
"""

import asyncio
import logging
import os
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# CHIRPS-based rainfall for May 2023 Northern Province event.
# Values reflect district-level averages; per-unit spatial variation is added
# via seeded noise so terrain differences (slope, TWI, NDVI) drive the risk
# distribution naturally — producing a realistic mix of risk levels.
MAY_2023_RAINFALL = {
    "Musanze": {"daily_mm": 42.0, "antecedent_5day_mm": 118.0, "antecedent_3day_mm": 72.0, "antecedent_10day_mm": 160.0},
    "Gakenke": {"daily_mm": 36.0, "antecedent_5day_mm": 102.0, "antecedent_3day_mm": 62.0, "antecedent_10day_mm": 140.0},
    "Burera":  {"daily_mm": 26.0, "antecedent_5day_mm":  82.0, "antecedent_3day_mm": 50.0, "antecedent_10day_mm": 115.0},
    "Gicumbi": {"daily_mm": 20.0, "antecedent_5day_mm":  68.0, "antecedent_3day_mm": 42.0, "antecedent_10day_mm":  96.0},
}


async def replay():
    import pandas as pd
    from motor.motor_asyncio import AsyncIOMotorClient
    from backend.app.ml.xgb_model import XGBModel
    from backend.app.config import get_settings

    settings = get_settings()
    client = AsyncIOMotorClient(os.getenv("MONGODB_URI"))
    db = client[os.getenv("MONGODB_DB_NAME", "landslide_ews")]

    logger.info("Loading all slope units from MongoDB ...")
    units = await db.slope_units.find({}).to_list(length=10000)
    logger.info("Found %d slope units", len(units))

    import random
    rng = random.Random(20230502)  # fixed seed → reproducible

    rows = []
    for u in units:
        district = u.get("district", "Musanze")
        rain = MAY_2023_RAINFALL.get(district, MAY_2023_RAINFALL["Musanze"])
        # ±20% spatial noise so terrain features drive the distribution
        daily = rain["daily_mm"]  * rng.uniform(0.80, 1.20)
        ant5  = rain["antecedent_5day_mm"] * rng.uniform(0.80, 1.20)
        rows.append({
            "unit_id":                  u["unit_id"],
            "slope_angle":              u.get("slope_angle", 0.0),
            "aspect":                   u.get("aspect", 0.0),
            "twi":                      u.get("twi", 0.0),
            "drainage_density":         u.get("drainage_density", 0.0),
            "ndvi":                     u.get("ndvi", 0.0),
            "soil_class":               u.get("soil_class", 0),
            "landuse_class":            u.get("landuse_class", 0),
            "daily_mm":                 daily,
            "antecedent_3day_mm":       rain["antecedent_3day_mm"] * rng.uniform(0.80, 1.20),
            "antecedent_5day_mm":       ant5,
            "antecedent_10day_mm":      rain["antecedent_10day_mm"] * rng.uniform(0.80, 1.20),
            "rainfall_intensity_ratio": round(daily / (ant5 + 1.0), 4),
        })

    feature_df = pd.DataFrame(rows)
    logger.info("Built feature matrix: %d rows", len(feature_df))

    model = XGBModel.load(settings.artifacts_path())
    predictions_df = model.predict(feature_df)

    alerts = int(predictions_df["alert_triggered"].sum())
    logger.info("Model done — %d units, %d alerts (threshold=%.2f)",
                len(predictions_df), alerts, model.production_threshold)

    unit_map = {u["unit_id"]: u for u in units}
    today = date.today().isoformat()
    await db.predictions.delete_many({"date": today})

    docs = []
    for _, row in predictions_df.iterrows():
        uid = int(row["unit_id"])
        u   = unit_map.get(uid, {})
        docs.append({
            "prediction_id":    str(uuid.uuid4()),
            "slope_unit_id":    uid,
            "district":         u.get("district", ""),
            "date":             today,
            "risk_probability": round(float(row["risk_probability"]), 4),
            "alert_triggered":  bool(row["alert_triggered"]),
            "top_features":     list(row["top_features"]),
            "scenario":         "may_2023_replay",
            "created_at":       datetime.utcnow().isoformat(),
        })

    await db.predictions.insert_many(docs)
    logger.info("Saved %d predictions as %s", len(docs), today)

    probs = predictions_df["risk_probability"]
    logger.info(
        "Risk distribution: critical(>=80%%)=%d  high(60-80%%)=%d  medium(40-60%%)=%d  low(<40%%)=%d",
        (probs >= 0.80).sum(), ((probs >= 0.60) & (probs < 0.80)).sum(),
        ((probs >= 0.40) & (probs < 0.60)).sum(), (probs < 0.40).sum(),
    )

    client.close()


if __name__ == "__main__":
    asyncio.run(replay())
