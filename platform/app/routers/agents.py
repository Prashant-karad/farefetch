from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Agent, BudgetPolicy
from app.services.auth import get_current_agent

router = APIRouter(prefix="/v1", tags=["agents"])


@router.get("/me")
async def me(agent: Agent = Depends(get_current_agent), session: AsyncSession = Depends(get_session)):
    """Who am I? The simplest way for an agent to check its API key works."""
    policy = await session.get(BudgetPolicy, agent.id)
    return {
        "agent_id": agent.id,
        "name": agent.name,
        "owner_id": agent.owner_id,
        "budget": None if policy is None else {
            "max_per_item": policy.max_per_item,
            "max_per_day": policy.max_per_day,
            "approval_threshold": policy.approval_threshold,
        },
    }