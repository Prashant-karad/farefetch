"""DEV ONLY: add money to the demo wallet without PayPal. Uses the real ledger.

Run from platform/:  python -m scripts.credit_wallet 5      (adds $5)
"""

import asyncio
import sys
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import Account, AgentOwner
from app.services.ledger import post_transaction

UNITS_PER_DOLLAR = 10_000


async def main(dollars: str) -> None:
    units = int(Decimal(dollars) * UNITS_PER_DOLLAR)  # Decimal: exact, unlike float
    async with SessionLocal() as session:
        owner = await session.scalar(select(AgentOwner).where(AgentOwner.email == "owner@example.com"))
        wallet = await session.scalar(
            select(Account).where(Account.type == "agent_wallet", Account.owner_id == owner.id)
        )
        txn = await post_transaction(
            session, type="topup", reference="dev-credit",
            entries=[("acc_paypal_clearing", -units), (wallet.id, units)],
        )
        await session.commit()
    await engine.dispose()
    print(f"Credited ${dollars} ({units} units) to {wallet.id} in transaction {txn.id}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "5"))