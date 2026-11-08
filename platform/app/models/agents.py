from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import TimestampMixin, new_id


class AgentOwner(TimestampMixin, Base):
    """The developer/company that owns agents and pays for them."""

    __tablename__ = "agent_owners"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("own"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)


class Agent(TimestampMixin, Base):
    """An AI agent. We NEVER store its API key, only a prefix (for lookup) and a hash."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("agt"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("agent_owners.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    api_key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class BudgetPolicy(Base):
    """Spending rules the owner sets for one agent. Amounts in units of $0.0001."""

    __tablename__ = "budget_policies"
    __table_args__ = (
        CheckConstraint("max_per_item > 0", name="ck_budget_max_per_item_positive"),
        CheckConstraint("max_per_day > 0", name="ck_budget_max_per_day_positive"),
    )

    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), primary_key=True)
    max_per_item: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_per_day: Mapped[int] = mapped_column(BigInteger, nullable=False)
    approval_threshold: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
