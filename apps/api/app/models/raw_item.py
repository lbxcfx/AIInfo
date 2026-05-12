from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonColumn, JsonDict, TimestampMixin, UUIDMixin


class RawItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "items_raw"
    __table_args__ = (
        UniqueConstraint("source_id", "raw_url", name="uq_items_raw_source_raw_url"),
    )

    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_title: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    fetch_status: Mapped[str] = mapped_column(String(40), nullable=False, default="ok")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[JsonDict] = mapped_column(JsonColumn, nullable=False, default=dict)

