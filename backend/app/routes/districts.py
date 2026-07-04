from fastapi import APIRouter
from ..database import get_db

router = APIRouter()

TARGET_DISTRICTS = ["Gakenke", "Burera", "Musanze", "Gicumbi"]


@router.get("/districts")
async def get_districts():
    """Per-district summary: highest risk unit, recent alert count, last update."""
    db = get_db()

    latest_pred = await db.predictions.find_one(sort=[("date", -1)])
    latest_date = latest_pred["date"] if latest_pred else None

    summaries = []
    for district in TARGET_DISTRICTS:
        unit_ids = await db.slope_units.distinct("unit_id", {"district": district})
        if not unit_ids:
            summaries.append({
                "district": district,
                "unit_count": 0,
                "highest_risk_probability": None,
                "highest_risk_unit_id": None,
                "recent_alert_count": 0,
                "last_update": None,
            })
            continue

        # Highest risk today
        top_pred = await db.predictions.find_one(
            {"slope_unit_id": {"$in": unit_ids}, "date": latest_date},
            sort=[("risk_probability", -1)],
        )

        # Alert count last 7 days
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
        pred_ids_recent = await db.predictions.distinct(
            "_id",
            {"slope_unit_id": {"$in": unit_ids}, "alert_triggered": True, "date": {"$gte": cutoff[:10]}},
        )
        alert_count = await db.alert_records.count_documents(
            {"prediction_id": {"$in": [str(p) for p in pred_ids_recent]}}
        )

        prob = top_pred["risk_probability"] if top_pred else None
        alert_level = None
        if prob and prob >= 0.80:
            alert_level = "EMERGENCY"
        elif prob and prob >= 0.60:
            alert_level = "WARNING"
        elif prob and prob >= 0.40:
            alert_level = "WATCH"

        # Get sector name for highest risk unit
        highest_sector = None
        if top_pred:
            unit_doc = await db.slope_units.find_one({"unit_id": top_pred["slope_unit_id"]})
            highest_sector = unit_doc.get("sector") if unit_doc else None

        summaries.append({
            "district": district,
            "unit_count": len(unit_ids),
            "highest_risk_probability": prob,
            "highest_risk_unit_id": top_pred["slope_unit_id"] if top_pred else None,
            "highest_risk_sector": highest_sector,
            "alert_level": alert_level,
            "recent_alert_count": alert_count,
            "last_update": latest_date,
        })

    return {"districts": summaries}
