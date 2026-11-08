from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import TimestampMixin, new_id


class AccessLog(TimestampMixin, Base):
    """Every request the gateway handles, paid or not. Feeds the publisher dashboard."""

    __tablename__ = "access_logs"
    __table_args__ = (
        CheckConstraint(
            "result IN ('payment_required', 'granted', 'unauthenticated', 'forbidden', 'invalid_pass', 'not_found')",
            name="ck_access_logs_result",
        ),
        Index("ix_access_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id"), nullable=True, index=True)
    resource_id: Mapped[str | None] = mapped_column(ForeignKey("resources.id"), nullable=True, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Purchase(TimestampMixin, Base):
    """Every purchase attempt, successful or not. Failures live here, NOT in the ledger."""

    __tablename__ = "purchases"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'completed', 'failed')", name="ck_purchases_status"),
        UniqueConstraint("agent_id", "idempotency_key", name="uq_purchases_agent_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("pur"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), nullable=False, index=True)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    failure_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)


class AccessGrant(Base):
    """A time pass: unlimited reads of one resource by one agent until expires_at."""

    __tablename__ = "access_grants"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'expired', 'revoked')", name="ck_access_grants_status"),
        # At most ONE active pass per (agent, resource): a partial unique index.
        Index(
            "uq_access_grants_one_active",
            "agent_id", "resource_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("grt"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), nullable=False)
    purchase_id: Mapped[str] = mapped_column(ForeignKey("purchases.id"), nullable=False, unique=True)
    license_id: Mapped[str] = mapped_column(ForeignKey("licenses.id"), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class UsageReceipt(TimestampMixin, Base):
    """Signed record of how purchased content was used in one answer."""

    __tablename__ = "usage_receipts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rcp"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False, index=True)
    answer_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    violations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
