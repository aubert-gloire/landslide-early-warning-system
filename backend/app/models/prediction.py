from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, Field
import uuid


class Prediction(BaseModel):
    prediction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slope_unit_id: int
    date: date
    risk_probability: float
    alert_triggered: bool
    top_features: list[tuple[str, float]] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
