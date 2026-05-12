from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.base import Base, TimestampMixin, UUIDMixin


class ItemEmbedding(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "item_embeddings"
    __table_args__ = (UniqueConstraint("item_id", name="uq_item_embeddings_item_id"),)

    item_id: Mapped[str] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    text_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
