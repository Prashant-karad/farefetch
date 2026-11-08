from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import TimestampMixin, new_id


class Account(TimestampMixin, Base):
    """A place money can sit. `balance` is a CACHE of SUM(ledger_entries.amount)."""

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "type IN ('agent_wallet', 'publisher_payable', 'platform_revenue', 'paypal_clearing')",
            name="ck_accounts_type",
        ),
        # Agent wallets can never go negative. Others may (corrections, outside money).
        CheckConstraint("type <> 'agent_wallet' OR balance >= 0", name="ck_accounts_wallet_non_negative"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("acc"))
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")


class Transaction(TimestampMixin, Base):
    """One real-world money event. Its ledger entries must sum to zero."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("type IN ('topup', 'purchase', 'payout', 'reversal')", name="ck_transactions_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("txn"))
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    reference: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)


class LedgerEntry(TimestampMixin, Base):
    """Append-only. Never UPDATE or DELETE rows here; fix mistakes with a reversal transaction."""

    __tablename__ = "ledger_entries"
    __table_args__ = (CheckConstraint("amount <> 0", name="ck_ledger_entries_nonzero"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # signed: + in, - out


class Topup(TimestampMixin, Base):
    __tablename__ = "topups"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_topups_amount_positive"),
        CheckConstraint("status IN ('created', 'completed', 'failed')", name="ck_topups_status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("top"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("agent_owners.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paypal_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="created")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Payout(TimestampMixin, Base):
    __tablename__ = "payouts"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payouts_amount_positive"),
        CheckConstraint("status IN ('pending', 'sent', 'completed', 'failed')", name="ck_payouts_status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("pay"))
    publisher_id: Mapped[str] = mapped_column(ForeignKey("publishers.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paypal_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
