from pydantic import BaseModel, Field
import uuid


class Recipient(BaseModel):
    recipient_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str          # E.164 format e.g. +250788000000
    district: str
    role: str = "district_officer"
    active: bool = True
