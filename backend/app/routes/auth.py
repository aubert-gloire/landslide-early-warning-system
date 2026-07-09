"""
Simple officer authentication for the Threshold dashboard.
POST /api/auth/login  — returns a session token valid for 24h.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_tokens: dict[str, dict] = {}

OFFICERS = [
    {"username": "gakenke", "name": "Field Officer", "district": "Gakenke"},
    {"username": "burera",  "name": "Field Officer", "district": "Burera"},
    {"username": "musanze", "name": "Field Officer", "district": "Musanze"},
    {"username": "gicumbi", "name": "Field Officer", "district": "Gicumbi"},
    {"username": "admin",   "name": "System Admin",  "district": "All Districts"},
    {"username": "guest",   "name": "Guest",         "district": "All Districts"},
]


class LoginRequest(BaseModel):
    username: str


@router.post("/auth/login")
async def login(body: LoginRequest):
    officer = next((o for o in OFFICERS if o["username"] == body.username.strip().lower()), None)
    if not officer:
        raise HTTPException(status_code=401, detail="Unknown username.")

    token = str(uuid.uuid4())
    _tokens[token] = {
        **officer,
        "expires": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
    }
    return {"token": token, "name": officer["name"], "district": officer["district"]}


@router.get("/auth/verify")
async def verify(token: str):
    entry = _tokens.get(token)
    if not entry:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    if datetime.utcnow() > datetime.fromisoformat(entry["expires"]):
        _tokens.pop(token, None)
        raise HTTPException(status_code=401, detail="Session expired.")
    return {"name": entry["name"], "district": entry["district"]}
