import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

TARGET_DISTRICTS = ["Gakenke", "Burera", "Musanze", "Gicumbi"]


@router.get("/districts")
async def get_districts():
    """Per-district summary: highest risk unit, recent alert count, last update."""
    try:
        return await _get_districts_inner()
    except Exception as exc:
        logger.exception("Error in /api/districts: %s", exc)
        return JSONResponse(status_code=500, content={"detail": str(exc)})


async def _get_districts_inner():
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

        # Average rainfall for district from latest records
        rain_agg = await db.rainfall_records.aggregate([
            {"$match": {"slope_unit_id": {"$in": unit_ids}}},
            {"$sort": {"date": -1}},
            {"$limit": len(unit_ids)},
            {"$group": {
                "_id": None,
                "avg_5day": {"$avg": "$antecedent_5day_mm"},
                "avg_daily": {"$avg": "$daily_mm"},
            }},
        ]).to_list(length=1)
        avg_5day  = round(rain_agg[0]["avg_5day"],  1) if rain_agg and rain_agg[0].get("avg_5day")  is not None else 0
        avg_daily = round(rain_agg[0]["avg_daily"], 1) if rain_agg and rain_agg[0].get("avg_daily") is not None else 0

        # Top features from highest-risk prediction
        top_features = top_pred.get("top_features", []) if top_pred else []

        summaries.append({
            "district": district,
            "unit_count": len(unit_ids),
            "highest_risk_probability": prob,
            "highest_risk_unit_id": top_pred["slope_unit_id"] if top_pred else None,
            "highest_risk_sector": highest_sector,
            "alert_level": alert_level,
            "recent_alert_count": alert_count,
            "last_update": latest_date,
            "avg_5day_mm": avg_5day,
            "avg_daily_mm": avg_daily,
            "top_features": top_features,
        })

    return {"districts": summaries}
