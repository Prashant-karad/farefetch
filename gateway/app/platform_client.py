import hashlib
import json

import httpx
import redis.asyncio as redis

from app.config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)
http = httpx.AsyncClient(
    base_url=settings.platform_url,
    timeout=5.0,  # never wait forever on another service
    headers={"X-Internal-Token": settings.internal_token},
)

MISSING = "__missing__"  # marker for "we checked, it doesn't exist"


async def get_resource(path: str) -> dict | None:
    """Price + license for a path. Cached in Redis so most requests skip the platform."""
    key = f"gw:resource:{path}"
    cached = await redis_client.get(key)
    if cached is not None:
        return None if cached == MISSING else json.loads(cached)

    resp = await http.get("/internal/resources/lookup", params={"path": path})
    if resp.status_code == 404:
        # Negative caching: remember "not found" too, so a bot hammering
        # random URLs can't hit the platform on every request.
        await redis_client.set(key, MISSING, ex=settings.resource_cache_seconds)
        return None
    resp.raise_for_status()
    data = resp.json()
    await redis_client.set(key, json.dumps(data), ex=settings.resource_cache_seconds)
    return data


async def verify_agent(api_key: str) -> dict | None:
    """Who owns this API key? Cached by the key's HASH; raw keys never go into Redis."""
    key = "gw:agent:" + hashlib.sha256(api_key.encode()).hexdigest()
    cached = await redis_client.get(key)
    if cached is not None:
        return None if cached == MISSING else json.loads(cached)

    resp = await http.post("/internal/agents/verify", json={"api_key": api_key})
    if resp.status_code == 401:
        await redis_client.set(key, MISSING, ex=10)  # short, so a fixed key works again quickly
        return None
    resp.raise_for_status()
    data = resp.json()
    await redis_client.set(key, json.dumps(data), ex=settings.agent_cache_seconds)
    return data


async def log_access(**fields) -> None:
    """Fire-and-forget. Logging must never break serving content."""
    try:
        await http.post("/internal/access-logs", json=fields)
    except httpx.HTTPError:
        pass  # production: push to a queue and retry instead of dropping