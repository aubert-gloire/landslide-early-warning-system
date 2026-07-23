"""
Admin authentication — credentials stored in MongoDB `users` collection.
Passwords are bcrypt-hashed. Plain-text is never persisted.

First-time setup: if no users exist, GET /api/auth/setup-required returns true,
and POST /api/auth/setup creates the first admin. After that, setup is locked.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import bcrypt as _bcrypt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from ..database import get_db

router = APIRouter()

_tokens: dict[str, dict] = {}


async def require_auth(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> dict:
    """
    FastAPI dependency gating every non-public route behind a valid session token.
    Accepts the token as `Authorization: Bearer <token>` (used by fetch calls) or
    as a `?token=` query param — the browser's native EventSource API (used for
    the /api/trigger/stream log viewer) cannot set custom headers, so it has no
    other way to authenticate.
    """
    tok = None
    if authorization and authorization.startswith("Bearer "):
        tok = authorization[len("Bearer "):]
    elif token:
        tok = token

    if not tok:
        raise HTTPException(status_code=401, detail="Missing authentication token.")

    entry = _tokens.get(tok)
    if not entry:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    if datetime.utcnow() > datetime.fromisoformat(entry["expires"]):
        _tokens.pop(tok, None)
        raise HTTPException(status_code=401, detail="Session expired.")
    return entry


def _hash(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


# ── First-time setup ──────────────────────────────────────────────────────────

@router.get("/auth/setup-required")
async def setup_required():
    db = get_db()
    count = await db.users.count_documents({})
    return {"required": count == 0}


class SetupRequest(BaseModel):
    password: str


@router.post("/auth/setup")
async def setup(body: SetupRequest):
    db = get_db()
    if await db.users.count_documents({}) > 0:
        raise HTTPException(status_code=403, detail="Admin account already exists.")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    await db.users.insert_one({
        "username": "admin",
        "password_hash": _hash(body.password),
        "name": "Admin",
        "role": "admin",
        "created_at": datetime.utcnow().isoformat(),
    })
    return {"ok": True}


# ── Login / verify ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(body: LoginRequest):
    db = get_db()
    user = await db.users.find_one({"username": body.username.strip().lower()})

    if not user or not _verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = str(uuid.uuid4())
    _tokens[token] = {
        "name": user["name"],
        "district": "All Districts",
        "expires": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
    }
    return {"token": token, "name": user["name"], "district": "All Districts"}


@router.post("/auth/guest")
async def guest_login():
    token = str(uuid.uuid4())
    _tokens[token] = {
        "name": "Guest",
        "district": "All Districts",
        "expires": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
    }
    return {"token": token, "name": "Guest", "district": "All Districts"}


@router.get("/auth/verify")
async def verify(token: str):
    entry = _tokens.get(token)
    if not entry:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    if datetime.utcnow() > datetime.fromisoformat(entry["expires"]):
        _tokens.pop(token, None)
        raise HTTPException(status_code=401, detail="Session expired.")
    return {"name": entry["name"], "district": entry["district"]}
