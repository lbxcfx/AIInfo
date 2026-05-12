"""create raw items and normalized items

Revision ID: 20260511_0002
Revises: 20260511_0001
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260511_0002"
down_revision: str | None = "20260511_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "items_raw",
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("raw_url", sa.Text(), nullable=False),
        sa.Column("fetched_url", sa.Text(), nullable=False),
        sa.Column("raw_title", sa.Text(), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=96), nullable=False),
        sa.Column("fetch_status", sa.String(length=40), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name=op.f("fk_items_raw_source_id_sources"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_items_raw")),
        sa.UniqueConstraint("source_id", "raw_url", name="uq_items_raw_source_raw_url"),
    )
    op.create_index(op.f("ix_items_raw_content_hash"), "items_raw", ["content_hash"], unique=False)
    op.create_index(op.f("ix_items_raw_source_id"), "items_raw", ["source_id"], unique=False)

    op.create_table(
        "items",
        sa.Column("raw_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title_original", sa.Text(), nullable=False),
        sa.Column("title_zh", sa.Text(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("summary_short", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("normalized_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_ai_related", sa.Boolean(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("is_featured", sa.Boolean(), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
        sa.Column("duplicate_of", sa.String(length=64), nullable=True),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["raw_id"], ["items_raw.id"], name=op.f("fk_items_raw_id_items_raw"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name=op.f("fk_items_source_id_sources"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_items")),
        sa.UniqueConstraint("canonical_url", name="uq_items_canonical_url"),
        sa.UniqueConstraint("raw_id", name=op.f("uq_items_raw_id")),
    )
    op.create_index(op.f("ix_items_raw_id"), "items", ["raw_id"], unique=False)
    op.create_index(op.f("ix_items_source_id"), "items", ["source_id"], unique=False)

    op.create_table(
        "source_health",
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("new_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name=op.f("fk_source_health_source_id_sources"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_health")),
    )
    op.create_index(op.f("ix_source_health_source_id"), "source_health", ["source_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_source_health_source_id"), table_name="source_health")
    op.drop_table("source_health")
    op.drop_index(op.f("ix_items_source_id"), table_name="items")
    op.drop_index(op.f("ix_items_raw_id"), table_name="items")
    op.drop_table("items")
    op.drop_index(op.f("ix_items_raw_source_id"), table_name="items_raw")
    op.drop_index(op.f("ix_items_raw_content_hash"), table_name="items_raw")
    op.drop_table("items_raw")
