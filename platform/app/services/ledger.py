from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, LedgerEntry, Transaction


class InsufficientFunds(Exception):
    """A wallet would go below zero."""


class UnbalancedTransaction(Exception):
    """Entries don't sum to zero. Always a bug in the caller."""


async def post_transaction(
    session: AsyncSession,
    *,
    type: str,
    reference: str,
    entries: list[tuple[str, int]],
    idempotency_key: str | None = None,
) -> Transaction:
    """Record one money event as balanced ledger entries and update cached balances.

    Does NOT commit: the caller decides when the whole unit of work is saved.
    """
    entries = [(account_id, amount) for account_id, amount in entries if amount != 0]
    if not entries or sum(amount for _, amount in entries) != 0:
        raise UnbalancedTransaction(f"entries must sum to zero: {entries}")

    txn = Transaction(type=type, reference=reference, idempotency_key=idempotency_key)
    session.add(txn)
    await session.flush()

    # Always touch accounts in the same order to avoid deadlocks.
    for account_id, amount in sorted(entries):
        result = await session.execute(
            update(Account)
            .where(Account.id == account_id)
            # Check and change in ONE statement: wallets can't go below zero.
            .where((Account.type != "agent_wallet") | (Account.balance + amount >= 0))
            .values(balance=Account.balance + amount)
            .returning(Account.id)
            .execution_options(synchronize_session=False)
        )
        if result.scalar_one_or_none() is None:
            raise InsufficientFunds(account_id)
        session.add(LedgerEntry(transaction_id=txn.id, account_id=account_id, amount=amount))

    await session.flush()
    return txn