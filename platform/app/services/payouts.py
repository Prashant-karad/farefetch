"""Settle publisher earnings through PayPal Payouts.

Order of operations (each step survives a crash at any point):
  1. DB transaction: lock publisher balances, move money out of them in the ledger,
     create Payout rows as 'pending'. COMMIT.
  2. Call PayPal (outside any DB transaction).
  3. Success -> mark 'sent'. Failure -> post REVERSAL transactions and mark 'failed'.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Payout, Publisher
from app.services import paypal_client
from app.services.ledger import post_transaction
from app.services.paypal_client import PayPalError

UNITS_PER_CENT = 100            # 1 unit = $0.0001
MIN_PAYOUT_UNITS = 100          # $0.01
CLEARING = "acc_paypal_clearing"


def units_to_usd(units: int) -> str:
    cents = units // UNITS_PER_CENT
    return f"{cents // 100}.{cents % 100:02d}"


async def settle_publishers(session: AsyncSession) -> dict:
    batch_id = f"ffb_{uuid.uuid4().hex[:16]}"

    # 1. Reserve the money in our books.
    rows = (await session.execute(
        select(Account, Publisher)
        .join(Publisher, Publisher.id == Account.owner_id)
        .where(Account.type == "publisher_payable")
        .order_by(Account.id)
        .with_for_update(of=Account)
    )).all()

    payouts: list[tuple[Payout, Publisher]] = []
    for account, publisher in rows:
        amount = (account.balance // UNITS_PER_CENT) * UNITS_PER_CENT  # whole cents only; remainder waits
        if amount < MIN_PAYOUT_UNITS:
            continue
        payout = Payout(publisher_id=publisher.id, amount=amount, status="pending")
        session.add(payout)
        await session.flush()
        await post_transaction(
            session, type="payout", reference=payout.id,
            entries=[(account.id, -amount), (CLEARING, amount)],
            idempotency_key=f"payout:{payout.id}",
        )
        payouts.append((payout, publisher))
    await session.commit()

    if not payouts:
        return {"batch_id": None, "status": "nothing_to_pay", "payouts": []}

    # 2. Ask PayPal to send the money.
    try:
        result = await paypal_client.create_payout_batch(batch_id=batch_id, items=[
            {"payout_id": p.id, "email": pub.paypal_email, "amount_value": units_to_usd(p.amount)}
            for p, pub in payouts
        ])
        paypal_batch_id = result["batch_header"]["payout_batch_id"]
        for p, _ in payouts:
            p.status = "sent"
            p.paypal_batch_id = paypal_batch_id
        await session.commit()
        status = result["batch_header"].get("batch_status", "PENDING")
    except (PayPalError, KeyError) as exc:
        # 3. PayPal refused: give the money back to the publishers in our books.
        for p, _ in payouts:
            account = await session.scalar(
                select(Account).where(Account.type == "publisher_payable", Account.owner_id == p.publisher_id)
            )
            await post_transaction(
                session, type="reversal", reference=p.id,
                entries=[(CLEARING, -p.amount), (account.id, p.amount)],
                idempotency_key=f"payout-reversal:{p.id}",
            )
            p.status = "failed"
        await session.commit()
        return {"batch_id": batch_id, "status": "failed", "error": str(exc)[:500],
                "payouts": [{"payout_id": p.id, "publisher": pub.name, "amount_usd": units_to_usd(p.amount)}
                            for p, pub in payouts]}

    return {
        "batch_id": batch_id,
        "paypal_batch_id": paypal_batch_id,
        "status": status,
        "payouts": [{"payout_id": p.id, "publisher": pub.name, "email": pub.paypal_email,
                     "amount_usd": units_to_usd(p.amount)} for p, pub in payouts],
    }


async def refresh_payout_status(session: AsyncSession, paypal_batch_id: str) -> dict:
    """Ask PayPal how the batch is doing and mark our payouts 'completed' when it succeeds."""
    batch = await paypal_client.get_payout_batch(paypal_batch_id)
    status = batch["batch_header"]["batch_status"]
    if status == "SUCCESS":
        payouts = (await session.scalars(select(Payout).where(Payout.paypal_batch_id == paypal_batch_id))).all()
        for p in payouts:
            p.status = "completed"
        await session.commit()
    return {"paypal_batch_id": paypal_batch_id, "status": status,
            "items": [{"receiver": i["payout_item"]["receiver"], "status": i["transaction_status"]}
                      for i in batch.get("items", [])]}
