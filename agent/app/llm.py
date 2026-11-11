import json

import httpx

from app import config

_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def enabled() -> bool:
    return bool(config.GEMINI_API_KEY)


def _call(prompt: str, json_mode: bool, temperature: float) -> str | None:
    if not enabled():
        return None
    gen = {"temperature": temperature}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    try:
        resp = httpx.post(_URL.format(model=config.LLM_MODEL), params={"key": config.GEMINI_API_KEY},
                          json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                "generationConfig": gen}, timeout=60.0)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


def generate_json(prompt: str, temperature: float = 0.2) -> dict | None:
    text = _call(prompt, True, temperature)
    try:
        return json.loads(text) if text else None
    except json.JSONDecodeError:
        return None


def generate_text(prompt: str, temperature: float = 0.4) -> str | None:
    return _call(prompt, False, temperature)
