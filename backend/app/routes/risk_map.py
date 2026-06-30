from datetime import date

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
