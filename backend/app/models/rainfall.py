from datetime import date
from pydantic import BaseModel


class RainfallRecord(BaseModel):
    slope_unit_id: int
    date: date
    daily_mm: float
    antecedent_5day_mm: float
