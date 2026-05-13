from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonColumn, JsonDict, TimestampMixin, UUIDMixin


class WechatDraft(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "wechat_drafts"

    item_id: Mapped[str] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    draft_type: Mapped[str] = mapped_column(String(80), nullable=False, default="github_project")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    digest: Mapped[str] = mapped_column(Text, nullable=False, default="")
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    image_plan: Mapped[JsonDict] = mapped_column(JsonColumn, nullable=False, default=dict)
    style_notes: Mapped[JsonDict] = mapped_column(JsonColumn, nullable=False, default=dict)
    submission_status: Mapped[str] = mapped_column(String(40), nullable=False, default="drafted")
    submit_result: Mapped[JsonDict] = mapped_column(JsonColumn, nullable=False, default=dict)
