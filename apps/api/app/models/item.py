from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonColumn, JsonDict, TimestampMixin, UUIDMixin


class Item(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("canonical_url", name="uq_items_canonical_url"),)

    raw_id: Mapped[str] = mapped_column(
        ForeignKey("items_raw.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title_original: Mapped[str] = mapped_column(Text, nullable=False)
    title_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary_short: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="en")
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="行业动态")
    entities: Mapped[JsonDict] = mapped_column(JsonColumn, nullable=False, default=dict)
    score_details: Mapped[JsonDict] = mapped_column(JsonColumn, nullable=False, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    normalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_ai_related: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_of: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(40), nullable=False, default="processed")
    llm_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
