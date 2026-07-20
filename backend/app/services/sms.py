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


async def _send_via_africastalking(phone: str, message: str) -> dict:
    """Send via Africa's Talking. Returns {success, raw_status, error}."""
    settings = get_settings()
    sms = _init_at()
    raw_sender = (settings.at_sender_id or "").strip().strip('"').strip("'")
    sender = raw_sender if raw_sender else None
    response = sms.send(message, [phone], sender_id=sender)
    recipients = response.get("SMSMessageData", {}).get("Recipients", [])
    if not recipients:
        detail = response.get("SMSMessageData", {}).get("Message", "no recipients in response")
        return {"success": False, "raw_status": "no_recipients", "error": detail}
    status = recipients[0].get("status", "failed")
    success = "Success" in status
    return {"success": success, "raw_status": status, "error": None if success else status}


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
    # not final delivery (that arrives later via webhook) — only treat its
    # own explicit failure/cancellation statuses as a failure here.
    success = status not in ("failed", "failed_queued", "not_delivered", "cancelled")
    return {"success": success, "raw_status": status, "error": None if success else status}


async def _dispatch_sms(phone: str, message: str) -> dict:
    """
    Fan out to all configured SMS providers in parallel.
    Returns {"overall": "sent"|"failed", "providers": {name: raw_status}, "errors": {name: error}}.
    Configure via SMS_PROVIDER env var — comma-separated:
      "africastalking"            → AT only
      "telerivet"                 → Telerivet only
      "africastalking,telerivet"  → both simultaneously
    """
    import asyncio as _asyncio

    settings = get_settings()
    providers = [p.strip() for p in settings.sms_provider.lower().split(",") if p.strip()]
    logger.info("SMS dispatch via providers=%s to=%s", providers, phone)

    async def try_provider(name: str) -> tuple[str, dict]:
        try:
            result = (
                await _send_via_telerivet(phone, message) if name == "telerivet"
                else await _send_via_africastalking(phone, message)
            )
            logger.info("Provider %s → %s", name, result["raw_status"])
            return name, result
        except Exception as exc:
            logger.error("Provider %s failed: %s", name, exc)
            return name, {"success": False, "raw_status": "exception", "error": str(exc)}

    results = await _asyncio.gather(*[try_provider(p) for p in providers])
    provider_status = {name: r["raw_status"] for name, r in results}
    provider_errors = {name: r["error"] for name, r in results if r.get("error")}
    overall = "sent" if any(r["success"] for _, r in results) else "failed"
    return {"overall": overall, "providers": provider_status, "errors": provider_errors}


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
