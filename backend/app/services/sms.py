"""
Telerivet SMS integration (routes through a real Android SIM via route_id).

Inbound SMS webhook: Telerivet posts to /api/sms/telerivet-callback when an
officer replies. Reply format expected from officers: "YES <unit_id>" or "NO <unit_id>"

Africa's Talking was evaluated and removed 2026-07-23 — see
docs/africastalking-investigation.md for the full writeup. Summary: AT's
shared/anonymous sender pool (the only option without a paid, telco-approved
alphanumeric sender ID) is unreliable on MTN Rwanda. Tested across 2 AT
accounts, 3 phone numbers, and both short and full alert-format messages —
consistently "Rejected" on AT's own delivery log, including the exact same
message text (byte-for-byte) that had succeeded via the same account and
number four months earlier. Content, account, and destination were all
ruled out as the cause; the most likely explanation is that MTN/AT's
shared-pool filtering rules tightened between then and now — a carrier-side
change outside this project's control.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from ..config import get_settings
from ..database import get_db

logger = logging.getLogger(__name__)


ALERT_LEVELS = {
    "WATCH":      (0.40, 0.60, "Elevated risk. Monitor closely."),
    "WARNING":    (0.60, 0.80, "High risk. Prepare evacuation advisory."),
    "EMERGENCY":  (0.80, 1.01, "CRITICAL. Activate MINEMA now."),
}


def get_alert_level(prob: float) -> tuple[str, str]:
    """Returns (level_name, action_text) for a given probability."""
    for level, (lo, hi, action) in ALERT_LEVELS.items():
        if lo <= prob < hi:
            return level, action
    return "WATCH", ALERT_LEVELS["WATCH"][2]


def build_alert_message(
    district: str,
    unit_id: int,
    risk_probability: float,
    top_features: list[tuple[str, float]],
    sector: str = "",
    centroid_lat: float | None = None,
    centroid_lon: float | None = None,
    rainfall_available: bool = True,
) -> str:
    prob_pct = int(risk_probability * 100)
    level, action = get_alert_level(risk_probability)
    driver = top_features[0][0].replace("_", " ") if top_features else ""
    location = f"{district}/{sector}" if sector else district
    # .5f (~1m precision) — a slope unit averages ~0.8km², so the earlier
    # .2f (~1.1km precision) put the GPS error on the same scale as the
    # unit itself, giving officers a coordinate no more useful than the
    # district/sector name already printed above it.
    gps = f" {centroid_lat:.5f},{centroid_lon:.5f}" if centroid_lat is not None else ""
    note = "\nNOTE: rainfall data unavailable today, based on terrain only" if not rainfall_available else ""
    return (
        f"LSEWS {level} {location}{gps}\n"
        f"Unit:{unit_id} Risk:{prob_pct}% Driver:{driver}\n"
        f"{action}{note}\n"
        f"Reply YES {unit_id} or NO {unit_id}"
    )


async def _send_via_telerivet(phone: str, message: str) -> dict:
    """Send via Telerivet REST API (routes through Android SIM if route_id set)."""
    settings = get_settings()
    if not settings.telerivet_api_key or not settings.telerivet_project_id:
        return {
            "success": False, "raw_status": "not_configured",
            "error": "TELERIVET_API_KEY / TELERIVET_PROJECT_ID not set",
        }
    url = f"https://api.telerivet.com/v1/projects/{settings.telerivet_project_id}/messages/send"
    payload: dict = {"to_number": phone, "content": message}
    if settings.telerivet_route_id:
        payload["route_id"] = settings.telerivet_route_id
    # Ask Telerivet to POST a real delivery confirmation back to us later —
    # without this, "queued" is the last status we ever see, and we'd have
    # no basis to ever show "delivered" as anything but a guess.
    if settings.public_api_base_url and settings.telerivet_status_secret:
        payload["status_url"] = f"{settings.public_api_base_url}/api/sms/telerivet-status"
        payload["status_secret"] = settings.telerivet_status_secret
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            auth=(settings.telerivet_api_key, ""),
            json=payload,
        )
    if resp.status_code >= 400:
        # Surface Telerivet's actual error body instead of raising a bare
        # HTTPStatusError — a wrong project ID, an unverified/misconfigured
        # route_id, or an out-of-credit account all return 4xx here, and the
        # body is the only place that says which one.
        return {"success": False, "raw_status": f"http_{resp.status_code}", "error": resp.text[:300]}
    data = resp.json()
    status = data.get("status", "unknown")
    logger.info("Telerivet response: id=%s status=%s route=%s", data.get("id"), status, settings.telerivet_route_id or "default")
    # Telerivet's send response reflects acceptance into its outbound queue,
    # not final delivery (that arrives later via the status webhook, if
    # configured) — only treat its own explicit failure/cancellation
    # statuses as a failure here.
    success = status not in ("failed", "failed_queued", "not_delivered", "cancelled")
    return {"success": success, "raw_status": status, "error": None if success else status, "message_id": data.get("id")}


async def _dispatch_sms(phone: str, message: str) -> dict:
    """
    Send via Telerivet — the only SMS provider (see module docstring for why
    Africa's Talking was removed). Kept in this {"overall", "providers",
    "errors"} shape, rather than flattened, so AlertRecord.provider_status /
    provider_errors and the frontend's existing per-provider rendering
    (AlertTable.jsx) don't need to change for a single-provider setup.
    """
    logger.info("SMS dispatch via telerivet to=%s", phone)
    try:
        result = await _send_via_telerivet(phone, message)
        logger.info("Provider telerivet → %s", result["raw_status"])
    except Exception as exc:
        logger.error("Provider telerivet failed: %s", exc)
        result = {"success": False, "raw_status": "exception", "error": str(exc)}

    provider_status = {"telerivet": result["raw_status"]}
    provider_errors = {"telerivet": result["error"]} if result.get("error") else {}
    overall = "sent" if result["success"] else "failed"
    return {
        "overall": overall, "providers": provider_status, "errors": provider_errors,
        "telerivet_message_id": result.get("message_id"),
    }


async def send_alert(
    phone: str,
    recipient_id: str,
    prediction_id: str,
    district: str,
    unit_id: int,
    risk_probability: float,
    top_features: list[tuple[str, float]],
    sector: str = "",
    centroid_lat: float | None = None,
    centroid_lon: float | None = None,
    rainfall_available: bool = True,
) -> str:
    """Send SMS alert and write AlertRecord to MongoDB. Returns alert_id."""
    from ..models.alert import AlertRecord
    import uuid

    settings = get_settings()
    message = build_alert_message(
        district, unit_id, risk_probability, top_features, sector,
        centroid_lat, centroid_lon, rainfall_available,
    )
    alert_id = str(uuid.uuid4())

    alert = AlertRecord(
        alert_id=alert_id,
        prediction_id=prediction_id,
        recipient_id=recipient_id,
        message=message,
        delivery_status="pending",
        district=district,
        slope_unit_id=unit_id,
        risk_probability=risk_probability,
        rainfall_available=rainfall_available,
    )

    db = get_db()
    await db.alert_records.insert_one(alert.model_dump())

    try:
        dispatch = await _dispatch_sms(phone, message)
    except Exception as e:
        logger.error("SMS dispatch failed for %s: %s", phone, e)
        dispatch = {"overall": "failed", "providers": {}, "errors": {"dispatch": str(e)}}

    await db.alert_records.update_one(
        {"alert_id": alert_id},
        {"$set": {
            "delivery_status": dispatch["overall"],
            "provider_status": dispatch["providers"],
            "provider_errors": dispatch["errors"],
            "telerivet_message_id": dispatch.get("telerivet_message_id"),
        }},
    )
    logger.info(
        "SMS %s → %s (status=%s, providers=%s)",
        alert_id, phone, dispatch["overall"], dispatch["providers"],
    )
    return alert_id


async def handle_inbound(phone: str, message: str):
    """
    Process officer SMS reply and update AlertRecord.feedback.
    Expected format: "YES <unit_id>" or "NO <unit_id>"
    """
    db = get_db()
    message = message.strip().upper()
    parts = message.split()
    if not parts or parts[0] not in ("YES", "NO"):
        logger.info("Unrecognized SMS reply from %s: %s", phone, message)
        return

    confirmed = parts[0] == "YES"
    # Match to a recent unacknowledged alert from this phone
    cutoff = datetime.utcnow() - timedelta(hours=24)
    recipient = await db.recipients.find_one({"phone": phone})
    if not recipient:
        logger.warning("Inbound SMS from unknown phone %s", phone)
        return

    alert = await db.alert_records.find_one(
        {
            "recipient_id": recipient["recipient_id"],
            "sent_at": {"$gte": cutoff},
            "feedback": None,
        },
        sort=[("sent_at", -1)],
    )
    if not alert:
        logger.info("No pending alert to match for %s", phone)
        return

    feedback_text = "CONFIRMED" if confirmed else "DENIED"
    await db.alert_records.update_one(
        {"alert_id": alert["alert_id"]},
        {"$set": {"feedback": feedback_text, "feedback_at": datetime.utcnow()}},
    )
    logger.info("Alert %s feedback: %s from %s", alert["alert_id"], feedback_text, phone)
