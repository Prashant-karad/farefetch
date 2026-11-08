from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import TimestampMixin, new_id


class Publisher(TimestampMixin, Base):
    __tablename__ = "publishers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("pub"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    paypal_email: Mapped[str] = mapped_column(String(320), nullable=False)


class License(Base):
    """Reusable license terms. Many resources point to the same license (normalization)."""

    __tablename__ = "licenses"
    __table_args__ = (
        CheckConstraint("type IN ('read', 'quote')", name="ck_licenses_type"),
        CheckConstraint("max_quote_words >= 0", name="ck_licenses_max_quote_words"),
        CheckConstraint("ttl_hours > 0", name="ck_licenses_ttl_positive"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    max_quote_words: Mapped[int] = mapped_column(Integer, nullable=False)
    attribution_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ttl_hours: Mapped[int] = mapped_column(Integer, nullable=False)


class Resource(TimestampMixin, Base):
    """Something an agent can buy access to: an article or an API endpoint."""

    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("kind IN ('article', 'api')", name="ck_resources_kind"),
        CheckConstraint("price > 0", name="ck_resources_price_positive"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("res"))
    publisher_id: Mapped[str] = mapped_column(ForeignKey("publishers.id"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 1 unit = $0.0001
    license_id: Mapped[str] = mapped_column(ForeignKey("licenses.id"), nullable=False)
    preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uniqueness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100, set by AI later
