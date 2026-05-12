from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonColumn, JsonDict, TimestampMixin, UUIDMixin


class LlmCall(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "llm_calls"

    item_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    task: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[JsonDict] = mapped_column(JsonColumn, nullable=False, default=dict)
    output_json: Mapped[JsonDict] = mapped_column(JsonColumn, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
