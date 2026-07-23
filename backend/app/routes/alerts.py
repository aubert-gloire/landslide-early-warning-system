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
    include_historical: bool = Query(default=False),
):
    """
    Returns alert history, newest first. Filter by district if provided.

    Historical backfill records (real risk crossed threshold on a past date,
    no SMS ever dispatched) are excluded by default so this log reads as what
    it's titled — an SMS dispatch log — matching /alerts/stats. Pass
    include_historical=true to see the full record including those.
    """
    db = get_db()
    query: dict = {} if include_historical else {"backfill_note": {"$exists": False}}

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
    """
    Summary stats for the feedback dashboard.

    Historical backfill records (real risk crossed threshold on a past date,
    but no SMS was ever dispatched — see backfill_note) are excluded from the
    headline counts so "Total Alerts Sent" means what it says. They're
    reported separately instead of being dropped, so the real historical
    record stays visible on the page, just not conflated with live dispatch
    performance.
    """
    db = get_db()
    real_query = {"backfill_note": {"$exists": False}}
    total = await db.alert_records.count_documents(real_query)
    confirmed = await db.alert_records.count_documents({**real_query, "feedback": "CONFIRMED"})
    denied = await db.alert_records.count_documents({**real_query, "feedback": "DENIED"})
    pending_feedback = await db.alert_records.count_documents({**real_query, "feedback": None})
    failed = await db.alert_records.count_documents({**real_query, "delivery_status": "failed"})
    historical_backfilled = await db.alert_records.count_documents({"backfill_note": {"$exists": True}})
    return {
        "total_alerts": total,
        "confirmed": confirmed,
        "denied": denied,
        "awaiting_feedback": pending_feedback,
        "delivery_failed": failed,
        "confirmation_rate": round(confirmed / total * 100, 1) if total > 0 else 0,
        "historical_backfilled": historical_backfilled,
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
