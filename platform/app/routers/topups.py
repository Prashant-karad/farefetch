from decimal import Decimal
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Agent, Topup
from app.services.auth import get_current_agent
from app.services.topups import TopupError, complete_topup, start_topup

router = APIRouter(prefix="/v1/topups", tags=["topups"])


class TopupRequest(BaseModel):
    amount: Decimal = Field(ge=Decimal("1.00"), le=Decimal("100.00"), max_digits=6, decimal_places=2)


def _usd(units: int) -> str:
    return f"${units // 10_000}.{units % 10_000:04d}"


@router.post("", status_code=201)
async def create_topup(body: TopupRequest, agent: Agent = Depends(get_current_agent),
                       session: AsyncSession = Depends(get_session)):
    """Start a PayPal top-up for this agent's owner. Open `approve_url` in a browser to pay."""
    try:
        return await start_topup(session, owner_id=agent.owner_id, amount=body.amount)
    except TopupError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message})


@router.get("/paypal/return", response_class=HTMLResponse)
async def paypal_return(token: str, session: AsyncSession = Depends(get_session)):
    """PayPal sends the buyer's browser here after approval. `token` is the PayPal order ID."""
    try:
        topup = await complete_topup(session, order_id=token)
    except TopupError as exc:
        return HTMLResponse(f"<h1>Top-up not completed</h1><p>{escape(exc.message)}</p>", status_code=exc.status)
    return HTMLResponse(f"<h1>✅ Top-up complete</h1><p>{_usd(topup.amount)} added to the wallet. "
                        "You can close this tab.</p>")


@router.get("/paypal/cancel", response_class=HTMLResponse)
async def paypal_cancel():
    return HTMLResponse("<h1>Top-up cancelled</h1><p>No money was taken.</p>")


@router.get("/{topup_id}")
async def get_topup(topup_id: str, agent: Agent = Depends(get_current_agent),
                    session: AsyncSession = Depends(get_session)):
    topup = await session.get(Topup, topup_id)
    if topup is None or topup.owner_id != agent.owner_id:
        # Same 404 for "doesn't exist" and "not yours": don't reveal other owners' top-ups.
        raise HTTPException(404, detail={"code": "topup_not_found", "message": "No such top-up"})
    return {"topup_id": topup.id, "status": topup.status, "amount": topup.amount,
            "paypal_order_id": topup.paypal_order_id}