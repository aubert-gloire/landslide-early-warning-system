"""
Africa's Talking SMS integration.
Sandbox mode during development; set AT_USERNAME to live username for production.

Inbound SMS webhook: Africa's Talking posts to /api/sms/callback when an officer replies.
Reply format expected from officers: "YES <unit_id>" or "NO <unit_id>"
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import africastalking
import httpx

from ..config import get_settings
from ..database import get_db

logger = logging.getLogger(__name__)


def _patch_requests_ssl():
    """
    Local antivirus/proxy intercepts TLS and breaks verify=True for AT sandbox.
    Patch requests.Session so all AT SDK calls use verify=False in dev.
    Render (production) has clean SSL — this function is never called there.
    """
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    _orig = requests.Session.request

    def _no_verify(self, method, url, **kwargs):
        kwargs.setdefault("verify", False)
        return _orig(self, method, url, **kwargs)

    requests.Session.request = _no_verify


def _init_at():
    settings = get_settings()
    username = settings.at_username.strip()
    if not settings.is_production:
        _patch_requests_ssl()
    africastalking.initialize(username, settings.at_api_key)
    logger.info("AT initialised — username=%s production=%s", username, settings.is_production)
    return africastalking.SMS


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
) -> str:
    prob_pct = int(risk_probability * 100)
    level, action = get_alert_level(risk_probability)
    driver = top_features[0][0].replace("_", " ") if top_features else ""
    location = f"{district}/{sector}" if sector else district
    gps = f" {centroid_lat:.2f},{centroid_lon:.2f}" if centroid_lat is not None else ""
    return (
        f"LSEWS {level} {location}{gps}\n"
        f"Unit:{unit_id} Risk:{prob_pct}% Driver:{driver}\n"
        f"{action}\n"
        f"Reply YES {unit_id} or NO {unit_id}"
    )


async def _send_via_africastalking(phone: str, message: str) -> str:
    """Send via Africa's Talking. Returns delivery status string."""
    settings = get_settings()
    sms = _init_at()
    raw_sender = (settings.at_sender_id or "").strip().strip('"').strip("'")
    sender = raw_sender if raw_sender else None
    response = sms.send(message, [phone], sender_id=sender)
    recipients = response.get("SMSMessageData", {}).get("Recipients", [])
    status = recipients[0].get("status", "failed") if recipients else "failed"
    return "sent" if "Success" in status else "failed"


async def _send_via_telerivet(phone: str, message: str) -> str:
    """Send via Telerivet REST API (routes through Android SIM if route_id set)."""
    settings = get_settings()
    if not settings.telerivet_api_key or not settings.telerivet_project_id:
        raise ValueError("TELERIVET_API_KEY and TELERIVET_PROJECT_ID must be set")
    url = f"https://api.telerivet.com/v1/projects/{settings.telerivet_project_id}/messages/send"
    payload: dict = {"to_number": phone, "content": message}
    if settings.telerivet_route_id:
        payload["route_id"] = settings.telerivet_route_id
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            auth=(settings.telerivet_api_key, ""),
            json=payload,
        )
    resp.raise_for_status()
    data = resp.json()
    status = data.get("status", "failed")
    logger.info("Telerivet response: id=%s status=%s route=%s", data.get("id"), status, settings.telerivet_route_id or "default")
    return "sent" if status in ("queued", "sending", "sent", "delivered") else "failed"


async def _dispatch_sms(phone: str, message: str) -> str:
    """
    Fan out to all configured SMS providers in parallel.
    Returns 'sent' if at least one provider succeeds, 'failed' if all fail.
    Configure via SMS_PROVIDER env var — comma-separated:
      "africastalking"            → AT only
      "telerivet"                 → Telerivet only
      "africastalking,telerivet"  → both simultaneously
    """
    import asyncio as _asyncio

    settings = get_settings()
    providers = [p.strip() for p in settings.sms_provider.lower().split(",") if p.strip()]
    logger.info("SMS dispatch via providers=%s to=%s", providers, phone)

    async def try_provider(name: str) -> tuple[str, str]:
        try:
            if name == "telerivet":
                status = await _send_via_telerivet(phone, message)
            else:
                status = await _send_via_africastalking(phone, message)
            logger.info("Provider %s → %s", name, status)
            return name, status
        except Exception as exc:
            logger.error("Provider %s failed: %s", name, exc)
            return name, "failed"

    results = await _asyncio.gather(*[try_provider(p) for p in providers])
    any_sent = any(status == "sent" for _, status in results)
    return "sent" if any_sent else "failed"


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
) -> str:
    """Send SMS alert and write AlertRecord to MongoDB. Returns alert_id."""
    from ..models.alert import AlertRecord
    import uuid

    settings = get_settings()
    message = build_alert_message(district, unit_id, risk_probability, top_features, sector, centroid_lat, centroid_lon)
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
    )

    db = get_db()
    await db.alert_records.insert_one(alert.model_dump())

    try:
        delivery_status = await _dispatch_sms(phone, message)
    except Exception as e:
        logger.error("SMS dispatch failed for %s: %s", phone, e)
        delivery_status = "failed"

    await db.alert_records.update_one(
        {"alert_id": alert_id},
        {"$set": {"delivery_status": delivery_status}},
    )
    logger.info("SMS %s → %s (status=%s)", alert_id, phone, delivery_status)
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
