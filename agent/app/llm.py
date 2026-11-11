"""LLM client for the agent: Groq (default) or Gemini. Returns None on failure (callers fall back)."""

import json
import re

import httpx

from app import config

DEFAULT_MODELS = {"groq": "openai/gpt-oss-120b", "gemini": "gemini-3.8-flash"}
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def model() -> str:
    return config.LLM_MODEL or DEFAULT_MODELS.get(config.LLM_PROVIDER, DEFAULT_MODELS["groq"])


def enabled() -> bool:
    return bool(config.GROQ_API_KEY if config.LLM_PROVIDER == "groq" else config.GEMINI_API_KEY)


def name() -> str:
    return f"{config.LLM_PROVIDER} ({model()})"


def _call(prompt: str, json_mode: bool, temperature: float) -> str | None:
    if not enabled():
        return None
    try:
        if config.LLM_PROVIDER == "groq":
            body = {"model": model(), "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}]}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}"}
            resp = httpx.post(GROQ_URL, json=body, headers=headers, timeout=60.0)
            if resp.status_code == 400 and json_mode:
                body.pop("response_format")
                resp = httpx.post(GROQ_URL, json=body, headers=headers, timeout=60.0)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        gen = {"temperature": temperature}
        if json_mode:
            gen["responseMimeType"] = "application/json"
        resp = httpx.post(GEMINI_URL.format(model=model()), params={"key": config.GEMINI_API_KEY},
                          json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                "generationConfig": gen}, timeout=60.0)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


def generate_json(prompt: str, temperature: float = 0.2) -> dict | None:
    text = _call(prompt + "\n\nRespond with a single JSON object only.", True, temperature)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        try:
            return json.loads(match.group(0)) if match else None
        except json.JSONDecodeError:
            return None


def generate_text(prompt: str, temperature: float = 0.4) -> str | None:
    return _call(prompt, False, temperature)
