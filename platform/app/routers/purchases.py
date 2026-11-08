from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Agent
from app.services.auth import get_current_agent
from app.services.purchases import PurchaseError, purchase_pass

router = APIRouter(prefix="/v1", tags=["purchases"])


class PurchaseRequest(BaseModel):
    resource_id: str
    reason: str | None = Field(default=None, max_length=1000)  # the agent's explanation


@router.post("/purchases", status_code=201)
async def create_purchase(
    body: PurchaseRequest,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str | None = Header(default=None, max_length=100),
):
    if not idempotency_key:
        raise HTTPException(400, detail={"code": "missing_idempotency_key",
                                         "message": "Send an Idempotency-Key header (unique per purchase attempt)"})
    try:
        return await purchase_pass(session, agent=agent, resource_id=body.resource_id,
                                   idempotency_key=idempotency_key, ai_reason=body.reason)
    except PurchaseError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message})