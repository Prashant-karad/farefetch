"""DEV ONLY: credit the demo wallet without PayPal, for local testing when no sandbox buyer is at hand.

It goes through the ledger like every other money movement (balanced entries, PayPal clearing account),
and the top-up row is labelled DEV-CREDIT so it can never be mistaken for a real PayPal payment.
For the demo, top up through PayPal Checkout instead.

Run from platform/:  python -m scripts.dev_credit 5.00
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.models import Account, AgentOwner, Topup
from app.services.ledger import post_transaction


async def main(amount: Decimal) -> None:
    units = int(amount * 10_000)
    async with SessionLocal() as session:
        owner = await session.scalar(select(AgentOwner).limit(1))
        wallet = await session.scalar(select(Account).where(Account.type == "agent_wallet", Account.owner_id == owner.id))
        topup = Topup(owner_id=owner.id, amount=units, status="completed",
                      paypal_order_id=f"DEV-CREDIT-{uuid.uuid4().hex[:8]}", completed_at=datetime.now(timezone.utc))
        session.add(topup)
        await session.flush()
        await post_transaction(session, type="topup", reference=topup.id,
                               entries=[("acc_paypal_clearing", -units), (wallet.id, units)],
                               idempotency_key=f"topup:{topup.id}")
        await session.commit()
    await engine.dispose()
    print(f"DEV credit of ${amount} added (not a PayPal payment).")


if __name__ == "__main__":
    asyncio.run(main(Decimal(sys.argv[1] if len(sys.argv) > 1 else "5.00")))
