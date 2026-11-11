import re

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Agent, BudgetPolicy, Publisher, Resource
from app.services.auth import get_current_agent
from app.services.budget_rules import parse_rule

router = APIRouter(prefix="/v1", tags=["catalog & budget"])

_STOP = {"the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "is", "what", "how", "when",
         "should", "do", "i", "my", "why", "does", "with", "before", "after"}


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 2}


@router.get("/catalog")
async def catalog(q: str | None = Query(default=None, max_length=300), limit: int = Query(default=10, ge=1, le=50),
                  session: AsyncSession = Depends(get_session)):
    """Discovery: what's for sale, with previews. Agents search this before requesting content.
    Ranking is simple keyword overlap (a real system would use search/embeddings)."""
    rows = (await session.execute(select(Resource, Publisher).join(Publisher))).all()
    query_terms = _terms(q) if q else set()
    scored = []
    for resource, publisher in rows:
        score = len(query_terms & _terms(f"{resource.title} {resource.preview}")) if query_terms else 1
        if score > 0:
            scored.append((score, resource, publisher))
    scored.sort(key=lambda t: (-t[0], t[1].price))
    return [{
        "resource_id": r.id, "path": r.path, "kind": r.kind, "title": r.title,
        "publisher": p.name, "price": r.price, "license_id": r.license_id,
        "preview": r.preview, "uniqueness_score": r.uniqueness_score, "match_score": s,
    } for s, r, p in scored[:limit]]


class NaturalRule(BaseModel):
    rule: str = Field(min_length=3, max_length=500)


@router.put("/agents/me/budget/natural")
async def set_budget_from_text(body: NaturalRule, agent: Agent = Depends(get_current_agent),
                               session: AsyncSession = Depends(get_session)):
    """Owner writes a spending rule in plain English; the AI turns it into enforced limits.
    Fields the rule doesn't mention keep their current values."""
    parsed = await parse_rule(body.rule)
    policy = await session.get(BudgetPolicy, agent.id)
    if policy is None:
        policy = BudgetPolicy(agent_id=agent.id, max_per_item=500, max_per_day=10_000)
        session.add(policy)
    if parsed["max_per_item"]:
        policy.max_per_item = parsed["max_per_item"]
    if parsed["max_per_day"]:
        policy.max_per_day = parsed["max_per_day"]
    if parsed["approval_threshold"] is not None:
        policy.approval_threshold = parsed["approval_threshold"]
    await session.commit()
    return {
        "rule": body.rule, "interpreted_by": parsed["source"], "explanation": parsed["explanation"],
        "policy": {"max_per_item": policy.max_per_item, "max_per_day": policy.max_per_day,
                   "approval_threshold": policy.approval_threshold},
    }
