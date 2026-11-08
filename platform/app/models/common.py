import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


def new_id(prefix: str) -> str:
    """Readable, random IDs like 'pur_3f9a1c...'. The prefix tells you the type at a glance."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class TimestampMixin:
    """Adds a created_at column, set by the DATABASE clock (not the app's)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
