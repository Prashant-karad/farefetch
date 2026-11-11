"""Tiny Gemini client returning JSON. Every caller has a deterministic fallback,
so the platform works (and demos) even without an API key."""

import json

import httpx

from app.config import settings

_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def enabled() -> bool:
    return bool(settings.gemini_api_key)


async def generate_json(prompt: str, *, temperature: float = 0.2) -> dict | None:
    """Ask the model for a JSON object. Returns None on any failure (callers fall back)."""
    if not enabled():
        return None
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _URL.format(model=settings.llm_model),
                params={"key": settings.gemini_api_key},
                json=body,
            )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception:
        return None


async def generate_text(prompt: str, *, temperature: float = 0.3) -> str | None:
    if not enabled():
        return None
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _URL.format(model=settings.llm_model),
                params={"key": settings.gemini_api_key},
                json=body,
            )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None
