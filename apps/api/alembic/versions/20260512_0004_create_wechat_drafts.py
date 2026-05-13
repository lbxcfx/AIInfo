"""create wechat drafts

Revision ID: 20260512_0004
Revises: 20260512_0003
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260512_0004"
down_revision: str | None = "20260512_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wechat_drafts",
        sa.Column("item_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("draft_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("digest", sa.Text(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("image_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("style_notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("submission_status", sa.String(length=40), nullable=False),
        sa.Column("submit_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name=op.f("fk_wechat_drafts_item_id_items"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wechat_drafts")),
    )
    op.create_index(op.f("ix_wechat_drafts_item_id"), "wechat_drafts", ["item_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_wechat_drafts_item_id"), table_name="wechat_drafts")
    op.drop_table("wechat_drafts")
