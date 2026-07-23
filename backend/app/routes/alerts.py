from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from ..database import get_db
from ..services.sms import handle_inbound
from .auth import require_auth

router = APIRouter()


@router.get("/alerts", dependencies=[Depends(require_auth)])
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


@router.get("/alerts/stats", dependencies=[Depends(require_auth)])
async def get_alert_stats():
    """Summary stats for the feedback dashboard."""
    db = get_db()
    total = await db.alert_records.count_documents({})
    confirmed = await db.alert_records.count_documents({"feedback": "CONFIRMED"})
    denied = await db.alert_records.count_documents({"feedback": "DENIED"})
    pending_feedback = await db.alert_records.count_documents({"feedback": None})
    failed = await db.alert_records.count_documents({"delivery_status": "failed"})
    return {
        "total_alerts": total,
        "confirmed": confirmed,
        "denied": denied,
        "awaiting_feedback": pending_feedback,
        "delivery_failed": failed,
        "confirmation_rate": round(confirmed / total * 100, 1) if total > 0 else 0,
    }


@router.post("/sms/telerivet-callback")
async def telerivet_inbound_webhook(request: Request):
    """
    Telerivet inbound SMS webhook.
    Telerivet posts JSON with: from_number, content, id, ...
    Configure in Telerivet dashboard → Project → Services → incoming message URL.
    """
    data = await request.json()
    phone = data.get("from_number", "")
    text = data.get("content", "")
    if phone and text:
        await handle_inbound(phone, text)
    return {"status": "ok"}
