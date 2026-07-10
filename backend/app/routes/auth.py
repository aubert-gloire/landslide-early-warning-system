"""
Admin authentication — credentials stored in MongoDB `users` collection.
Passwords are bcrypt-hashed. Plain-text is never persisted.

On first startup, if the `users` collection is empty and OFFICER_PASSWORD is set
in the environment, an admin account is seeded automatically.
After seeding, the password lives in the database and OFFICER_PASSWORD is no longer
needed for auth (though it can stay in env for the seed to be idempotent).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel

from ..config import Settings, get_settings
from ..database import get_db

router = APIRouter()

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_tokens: dict[str, dict] = {}


async def seed_admin_if_empty(officer_password: str) -> None:
    """Called at startup. Seeds one admin user if the users collection is empty."""
    if not officer_password:
        return
    db = get_db()
    if await db.users.count_documents({}) == 0:
        await db.users.insert_one({
            "username": "admin",
            "password_hash": _pwd.hash(officer_password),
            "name": "Admin",
            "role": "admin",
            "created_at": datetime.utcnow().isoformat(),
        })


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(body: LoginRequest, settings: Settings = Depends(get_settings)):
    db = get_db()
    user = await db.users.find_one({"username": body.username.strip().lower()})

    if not user or not _pwd.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = str(uuid.uuid4())
    _tokens[token] = {
        "name": user["name"],
        "district": "All Districts",
        "expires": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
    }
    return {"token": token, "name": user["name"], "district": "All Districts"}


@router.get("/auth/verify")
async def verify(token: str):
    entry = _tokens.get(token)
    if not entry:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    if datetime.utcnow() > datetime.fromisoformat(entry["expires"]):
        _tokens.pop(token, None)
        raise HTTPException(status_code=401, detail="Session expired.")
    return {"name": entry["name"], "district": entry["district"]}
