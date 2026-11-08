import hmac

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Agent
from app.services.security import hash_api_key


async def authenticate_api_key(session: AsyncSession, raw_key: str) -> Agent | None:
    """Find the agent by key prefix, then verify the full key by comparing hashes."""
    agent = await session.scalar(select(Agent).where(Agent.api_key_prefix == raw_key[:12]))
    if agent is None:
        return None
    # compare_digest takes the same time whether strings differ early or late,
    # so an attacker can't learn the hash from response timing.
    if not hmac.compare_digest(agent.api_key_hash, hash_api_key(raw_key)):
        return None
    return agent


def bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip() or None


async def get_current_agent(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> Agent:
    """FastAPI dependency: any endpoint that declares it requires a valid API key."""
    raw_key = bearer_token(authorization)
    if raw_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "missing_api_key", "message": "Send 'Authorization: Bearer <api key>'"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    agent = await authenticate_api_key(session, raw_key)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_api_key", "message": "API key is not valid"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return agent


async def require_internal(x_internal_token: str | None = Header(default=None)) -> None:
    """Only our own services (the gateway) may call /internal endpoints."""
    if x_internal_token is None or not hmac.compare_digest(x_internal_token, settings.internal_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Internal endpoint"},
        )