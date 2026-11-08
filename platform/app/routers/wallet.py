from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Account, Agent, LedgerEntry
from app.services.auth import get_current_agent

router = APIRouter(prefix="/v1", tags=["wallet"])


def format_usd(units: int) -> str:
    sign = "-" if units < 0 else ""
    units = abs(units)
    return f"{sign}${units // 10_000}.{units % 10_000:04d}"


@router.get("/wallet")
async def get_wallet(agent: Agent = Depends(get_current_agent), session: AsyncSession = Depends(get_session)):
    account = await session.scalar(
        select(Account).where(Account.type == "agent_wallet", Account.owner_id == agent.owner_id)
    )
    ledger_sum = await session.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(LedgerEntry.account_id == account.id)
    )
    entries = (
        await session.scalars(
            select(LedgerEntry).where(LedgerEntry.account_id == account.id)
            .order_by(LedgerEntry.id.desc()).limit(20)
        )
    ).all()
    return {
        "account_id": account.id,
        "balance": account.balance,
        "balance_display": format_usd(account.balance),
        "ledger_sum": ledger_sum,
        "in_sync": ledger_sum == account.balance,  # a mini reconciliation check
        "recent_entries": [
            {"id": e.id, "transaction_id": e.transaction_id, "amount": e.amount, "created_at": e.created_at.isoformat()}
            for e in entries
        ],
    }