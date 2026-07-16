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
    # Denormalized from prediction for fast alert-history display
    district: str | None = None
    slope_unit_id: int | None = None
    risk_probability: float | None = None
    rainfall_available: bool = True
    # Populated by inbound SMS webhook — officer confirms/denies landslide occurred
    feedback: str | None = None
    feedback_at: datetime | None = None
