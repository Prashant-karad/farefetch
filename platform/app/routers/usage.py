from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Agent, UsageReceipt
from app.services.auth import get_current_agent
from app.services.usage import UsageError, check_usage

router = APIRouter(prefix="/v1/usage", tags=["license guard"])


class UsageCheckRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=20_000)
    grant_ids: list[str] = Field(min_length=1, max_length=50)
    auto_fix: bool = True


@router.post("/check")
async def usage_check(body: UsageCheckRequest, agent: Agent = Depends(get_current_agent),
                      session: AsyncSession = Depends(get_session)):
    """License guard: verify an answer respects the licenses of the content it used.
    Repairs violations (LLM rewrite, else deterministic) and returns a signed usage receipt."""
    try:
        return await check_usage(session, agent=agent, answer=body.answer,
                                 grant_ids=body.grant_ids, auto_fix=body.auto_fix)
    except UsageError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message})


@router.get("/receipts/{receipt_id}")
async def get_receipt(receipt_id: str, session: AsyncSession = Depends(get_session)):
    """Public on purpose: publishers can fetch a receipt and verify its signature with the public key."""
    receipt = await session.get(UsageReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(404, detail={"code": "receipt_not_found", "message": "No such receipt"})
    return {"receipt_id": receipt.id, "agent_id": receipt.agent_id, "passed": receipt.passed,
            "answer_sha256": receipt.answer_sha256, "items": receipt.items,
            "violations_found": receipt.violations, "signature": receipt.signature,
            "created_at": receipt.created_at.isoformat()}
