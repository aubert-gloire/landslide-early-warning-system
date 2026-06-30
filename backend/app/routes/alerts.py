from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query, Request

from ..database import get_db
from ..services.sms import handle_inbound

router = APIRouter()


@router.get("/alerts")
async def get_alerts(
    district: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    skip: int = Query(default=0),
):
    """Returns alert history, newest first. Filter by district if provided."""
    db = get_db()
    query: dict = {}

    if district:
        # Join through predictions to filter by district
        unit_ids = await db.slope_units.distinct("unit_id", {"district": district})
        pred_ids = await db.predictions.distinct(
            "_id", {"slope_unit_id": {"$in": unit_ids}, "alert_triggered": True}
        )
        query["prediction_id"] = {"$in": [str(p) for p in pred_ids]}

    alerts = (
        await db.alert_records.find(query)
        .sort("sent_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )
    total = await db.alert_records.count_documents(query)

    for a in alerts:
        a["_id"] = str(a["_id"])

    return {"total": total, "skip": skip, "limit": limit, "alerts": alerts}


@router.post("/sms/callback")
async def sms_inbound_webhook(request: Request):
    """
    Africa's Talking inbound SMS callback.
    AT posts form data with: from, to, text, date, id, linkId
    """
    form = await request.form()
    phone = form.get("from", "")
    text = form.get("text", "")
    if phone and text:
        await handle_inbound(phone, text)
    return {"status": "ok"}
