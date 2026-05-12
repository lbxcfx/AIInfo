from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonColumn, JsonDict, TimestampMixin, UUIDMixin


class Source(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("url", name="uq_sources_url"),)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="rss")
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="T2")
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="en")
    category_hint: Mapped[str | None] = mapped_column(String(80), nullable=True)
    crawl_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reliability_score: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    extra: Mapped[JsonDict] = mapped_column(JsonColumn, nullable=False, default=dict)

