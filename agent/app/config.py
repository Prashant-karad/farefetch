"""Agent settings from environment or the repo's .env (no extra dependencies)."""

import os
from pathlib import Path


def _dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    for f in (Path(__file__).resolve().parents[2] / ".env", Path(".env")):
        if f.exists():
            for line in f.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    values.setdefault(k.strip(), v.strip())
    return values


_ENV = _dotenv()


def get(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name) or _ENV.get(name) or default


API_KEY = get("DEMO_AGENT_API_KEY")
GATEWAY_URL = get("GATEWAY_URL", "http://127.0.0.1:8000")
PLATFORM_URL = get("AGENT_PLATFORM_URL") or get("PLATFORM_URL", "http://127.0.0.1:8001")
GEMINI_API_KEY = get("GEMINI_API_KEY")
LLM_MODEL = get("LLM_MODEL", "gemini-2.0-flash")
