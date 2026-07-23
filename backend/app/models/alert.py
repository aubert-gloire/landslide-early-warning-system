from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
import uuid


class AlertRecord(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prediction_id: str
    recipient_id: str
    message: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    delivery_status: Literal["pending", "sent", "delivered", "failed"] = "pending"
    # Per-provider raw status/error — e.g. {"telerivet": "queued"} or
    # {"telerivet": "failed_queued"}. delivery_status above is just "did the
    # provider accept it"; these two show the raw status and why, instead of
    # collapsing everything into one "failed" badge. Kept dict-shaped (not
    # flattened) from when a second provider existed, so the frontend's
    # per-provider rendering doesn't need to change if one is ever added back.
    provider_status: dict[str, str] = {}
    provider_errors: dict[str, str] = {}
    # Denormalized from prediction for fast alert-history display
    district: str | None = None
    slope_unit_id: int | None = None
    risk_probability: float | None = None
    rainfall_available: bool = True
    # Populated by inbound SMS webhook — officer confirms/denies landslide occurred
    feedback: str | None = None
    feedback_at: datetime | None = None
