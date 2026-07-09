"""
Seed realistic demo data into MongoDB for the video demonstration.

Creates:
  - 4 sample recipients (one per district)
  - 14 days of predictions with realistic probability distributions
  - 3 alert records (simulating real fired alerts)

Run before recording the demo video:
  python scripts/seed_demo.py

The demo flow then is:
  1. Open dashboard → see colored map, district cards, recent alerts
  2. Click "Run Pipeline" (POST /api/trigger with high rainfall override)
  3. Watch map update, alert count increase
  4. Show SMS in Africa's Talking sandbox logs
"""

import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Musanze officer uses your real number from .env so you receive the test SMS.
# Other districts keep placeholder numbers (sandbox only, not real phones).
_test_phone = os.getenv("TEST_OFFICER_PHONE", "+250788000001")
_test_name  = os.getenv("TEST_OFFICER_NAME", "Test Officer")

DEMO_RECIPIENTS = [
    {"name": _test_name,        "phone": _test_phone,     "district": "Musanze", "role": "district_officer"},
    {"name": "Jeanne Mukamana", "phone": "+250788000002", "district": "Gakenke", "role": "district_officer"},
    {"name": "Patrick Habimana","phone": "+250788000003", "district": "Burera",  "role": "district_officer"},
    {"name": "Vestine Uwimana", "phone": "+250788000004", "district": "Gicumbi", "role": "district_officer"},
]

DISTRICTS = ["Musanze", "Gakenke", "Burera", "Gicumbi"]


async def seed():
    import os
    from motor.motor_asyncio import AsyncIOMotorClient
    import uuid
    import random

    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "landslide_ews")
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    # Recipients
    await db.recipients.delete_many({})
    recipient_docs = []
    for r in DEMO_RECIPIENTS:
        doc = {**r, "recipient_id": str(uuid.uuid4()), "active": True}
        recipient_docs.append(doc)
    await db.recipients.insert_many(recipient_docs)
    logger.info("Inserted %d recipients", len(recipient_docs))

    # Get slope units
    units = await db.slope_units.find({}).to_list(length=1000)
    if not units:
        logger.warning("No slope units in DB — run setup_db.py load first")
        client.close()
        return

    unit_by_district = {}
    for u in units:
        unit_by_district.setdefault(u.get("district", "Unknown"), []).append(u["unit_id"])

    # 14 days of predictions
    await db.predictions.delete_many({})
    all_preds = []
    prediction_id_map = {}

    rng = random.Random(42)
    for days_ago in range(14, 0, -1):
        pred_date = (date.today() - timedelta(days=days_ago)).isoformat()
        for district in DISTRICTS:
            unit_ids = unit_by_district.get(district, [])[:5]
            for unit_id in unit_ids:
                # Gradually increasing risk as we get closer to today
                base_prob = 0.10 + (14 - days_ago) * 0.03 + rng.uniform(-0.08, 0.15)
                if district == "Musanze" and days_ago <= 3:
                    base_prob = rng.uniform(0.72, 0.92)
                prob = max(0.0, min(0.99, base_prob))
                alert = prob >= 0.80
                pred_id = str(uuid.uuid4())
                doc = {
                    "prediction_id": pred_id,
                    "slope_unit_id": unit_id,
                    "date": pred_date,
                    "risk_probability": round(prob, 4),
                    "alert_triggered": alert,
                    "top_features": [["antecedent_5day_mm", 0.41], ["slope_angle", 0.23], ["twi", 0.15]],
                    "created_at": datetime.utcnow().isoformat(),
                }
                all_preds.append(doc)
                if alert:
                    prediction_id_map[pred_id] = {"district": district, "unit_id": unit_id, "prob": prob}

    if all_preds:
        await db.predictions.insert_many(all_preds)
        logger.info("Inserted %d predictions over 14 days", len(all_preds))

    # 3 alert records
    await db.alert_records.delete_many({})
    alert_docs = []
    for i, (pred_id, info) in enumerate(list(prediction_id_map.items())[:3]):
        recipient = next((r for r in recipient_docs if r["district"] == info["district"]), recipient_docs[0])
        alert_docs.append({
            "alert_id": str(uuid.uuid4()),
            "prediction_id": pred_id,
            "recipient_id": recipient["recipient_id"],
            "message": (
                f"[LSEWS ALERT] {info['district']} — Slope unit {info['unit_id']}: "
                f"{int(info['prob']*100)}% landslide risk. "
                f"Primary factors: antecedent 5day rainfall, slope angle. "
                f"Reply YES {info['unit_id']} to confirm. Follow official MINEMA protocols."
            ),
            "sent_at": (datetime.utcnow() - timedelta(hours=6-i*2)).isoformat(),
            "delivery_status": ["delivered", "sent", "delivered"][i],
            "feedback": ["CONFIRMED", None, None][i],
            "feedback_at": [(datetime.utcnow() - timedelta(hours=5)).isoformat(), None, None][i],
        })
    if alert_docs:
        await db.alert_records.insert_many(alert_docs)
        logger.info("Inserted %d alert records", len(alert_docs))

    client.close()
    logger.info("Demo seed complete. Dashboard is ready for recording.")


if __name__ == "__main__":
    asyncio.run(seed())
