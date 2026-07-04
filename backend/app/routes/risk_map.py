from datetime import date, datetime, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ..database import get_db

router = APIRouter()


@router.get("/risk-map")
async def get_risk_map(run_date: date | None = Query(default=None)):
    """
    Returns current GeoJSON FeatureCollection of slope-unit risk scores.
    If run_date is omitted, returns the most recent prediction date.
    """
    db = get_db()

    if run_date is None:
        latest = await db.predictions.find_one(sort=[("date", -1)])
        if not latest:
            return JSONResponse({"type": "FeatureCollection", "features": []})
        run_date = latest["date"]

    predictions = await db.predictions.find({"date": str(run_date)}).to_list(length=10000)
    if not predictions:
        return JSONResponse({"type": "FeatureCollection", "features": []})

    unit_ids = [p["slope_unit_id"] for p in predictions]
    units = await db.slope_units.find({"unit_id": {"$in": unit_ids}}).to_list(length=10000)
    unit_map = {u["unit_id"]: u for u in units}

    features = []
    for pred in predictions:
        unit = unit_map.get(pred["slope_unit_id"])
        if not unit or "geometry" not in unit:
            continue
        prob = pred["risk_probability"]
        risk_level = (
            "critical" if prob >= 0.80
            else "high" if prob >= 0.60
            else "medium" if prob >= 0.40
            else "low"
        )
        features.append({
            "type": "Feature",
            "geometry": unit["geometry"],
            "properties": {
                "unit_id": pred["slope_unit_id"],
                "district": unit.get("district", ""),
                "sector": unit.get("sector", ""),
                "risk_probability": prob,
                "risk_level": risk_level,
                "alert_triggered": pred["alert_triggered"],
                "top_features": pred.get("top_features", []),
                "date": pred["date"],
            },
        })

    return JSONResponse({
        "type": "FeatureCollection",
        "features": features,
        "metadata": {"date": str(run_date), "unit_count": len(features)},
    })


@router.get("/units/{unit_id}/rainfall")
async def get_unit_rainfall(unit_id: int, days: int = Query(default=10, le=30)):
    """Returns last N days of daily rainfall for a slope unit — used for popup sparkline."""
    db = get_db()
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)

    records = await db.rainfall_records.find(
        {
            "slope_unit_id": unit_id,
            "date": {"$gte": start.isoformat(), "$lte": end.isoformat()},
        },
        sort=[("date", 1)],
    ).to_list(length=days + 1)

    return {
        "unit_id": unit_id,
        "days": [{"date": r["date"], "daily_mm": round(r.get("daily_mm", 0), 1)} for r in records],
    }
