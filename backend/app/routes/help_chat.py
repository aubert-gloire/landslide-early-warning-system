"""
POST /api/help/ask — EWS Guide help chat.

RAG-constrained: retrieves the closest matching entries from the vetted
QA knowledge base (help_content.py) and asks Gemini to answer using ONLY
that material. This is a life-safety-adjacent tool, so it must never
improvise operational guidance — falls back to the plain rule-based
answer if Gemini is unavailable, misconfigured, or errors.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..config import get_settings
from ..services.help_content import rule_based_answer, top_matches

logger = logging.getLogger(__name__)
router = APIRouter()

GEMINI_MODEL = "gemini-flash-latest"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

SYSTEM_PROMPT = """You are the EWS Guide, a help assistant for a landslide early-warning \
system used by district emergency officers in Northern Province, Rwanda.

Rules:
- Answer ONLY using the "Reference material" below. Do not use outside knowledge.
- If the reference material doesn't cover the question, say so plainly and suggest \
2-3 related topics from the reference material instead of guessing.
- Never give real-time operational instructions (e.g. "evacuate now", "it is safe to stay") \
— always say alerts are decision support and defer to official MINEMA / Meteo Rwanda guidance.
- Keep answers short (3-6 sentences), plain language, no unexplained jargon.
- You may lightly rephrase the reference material for a natural, conversational tone, \
but do not add facts, numbers, or claims that aren't in it."""


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


@router.post("/help/ask")
async def ask_help(body: AskRequest):
    question = body.question.strip()
    settings = get_settings()

    matches = top_matches(question, k=3)
    if not matches:
        return {"answer": rule_based_answer(question), "source": "rule_based"}

    if not settings.gemini_api_key:
        return {"answer": rule_based_answer(question), "source": "rule_based"}

    reference = "\n\n".join(f"- {m['answer']}" for m in matches)
    prompt = f"{SYSTEM_PROMPT}\n\nReference material:\n{reference}\n\nQuestion: {question}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                GEMINI_URL,
                params={"key": settings.gemini_api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if not text:
            raise ValueError("empty response")
        return {"answer": text, "source": "gemini"}
    except Exception as exc:
        logger.warning("Gemini help request failed, falling back to rule-based: %s", exc)
        return {"answer": rule_based_answer(question), "source": "rule_based"}
