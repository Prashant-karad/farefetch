"""LLM client for Groq (default) or Gemini. Returns None on any failure,
and every caller has a deterministic fallback, so the platform never breaks without AI."""

import json
import re

import httpx

from app.config import settings

DEFAULT_MODELS = {"groq": "openai/gpt-oss-120b", "gemini": "gemini-3.8-flash"}
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def provider() -> str:
    return (settings.llm_provider or "groq").lower()


def model() -> str:
    return settings.llm_model or DEFAULT_MODELS.get(provider(), DEFAULT_MODELS["groq"])


def enabled() -> bool:
    return bool(settings.groq_api_key if provider() == "groq" else settings.gemini_api_key)


def _parse_json(text: str | None) -> dict | None:
    """Parse JSON even if the model wrapped it in prose or ``` fences."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


async def _groq(prompt: str, json_mode: bool, temperature: float) -> str | None:
    body = {"model": model(), "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(GROQ_URL, json=body, headers=headers)
        if resp.status_code == 400 and json_mode:
            # Some models don't support JSON mode: retry as plain text and parse leniently.
            body.pop("response_format")
            resp = await client.post(GROQ_URL, json=body, headers=headers)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _gemini(prompt: str, json_mode: bool, temperature: float) -> str | None:
    gen = {"temperature": temperature}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(GEMINI_URL.format(model=model()), params={"key": settings.gemini_api_key},
                                 json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                       "generationConfig": gen})
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _call(prompt: str, json_mode: bool, temperature: float) -> str | None:
    if not enabled():
        return None
    try:
        if provider() == "groq":
            return await _groq(prompt, json_mode, temperature)
        return await _gemini(prompt, json_mode, temperature)
    except Exception:
        return None


async def generate_json(prompt: str, *, temperature: float = 0.2) -> dict | None:
    return _parse_json(await _call(prompt + "\n\nRespond with a single JSON object only.", True, temperature))


async def generate_text(prompt: str, *, temperature: float = 0.3) -> str | None:
    return await _call(prompt, False, temperature)
