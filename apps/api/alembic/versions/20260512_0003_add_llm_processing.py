"""add llm processing audit and embeddings

Revision ID: 20260512_0003
Revises: 20260511_0002
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision: str = "20260512_0003"
down_revision: str | None = "20260511_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column(
            "score_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("items", sa.Column("llm_processed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "item_embeddings",
        sa.Column("item_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=96), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("text_preview", sa.Text(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name=op.f("fk_item_embeddings_item_id_items"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_item_embeddings")),
        sa.UniqueConstraint("item_id", name="uq_item_embeddings_item_id"),
    )
    op.create_index(op.f("ix_item_embeddings_content_hash"), "item_embeddings", ["content_hash"], unique=False)
    op.create_index(op.f("ix_item_embeddings_item_id"), "item_embeddings", ["item_id"], unique=False)

    op.create_table(
        "llm_calls",
        sa.Column("item_id", sa.String(length=64), nullable=True),
        sa.Column("task", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("input_hash", sa.String(length=96), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_calls")),
    )
    op.create_index(op.f("ix_llm_calls_input_hash"), "llm_calls", ["input_hash"], unique=False)
    op.create_index(op.f("ix_llm_calls_item_id"), "llm_calls", ["item_id"], unique=False)
    op.create_index(op.f("ix_llm_calls_status"), "llm_calls", ["status"], unique=False)
    op.create_index(op.f("ix_llm_calls_task"), "llm_calls", ["task"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_calls_task"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_status"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_item_id"), table_name="llm_calls")
    op.drop_index(op.f("ix_llm_calls_input_hash"), table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_index(op.f("ix_item_embeddings_item_id"), table_name="item_embeddings")
    op.drop_index(op.f("ix_item_embeddings_content_hash"), table_name="item_embeddings")
    op.drop_table("item_embeddings")
    op.drop_column("items", "llm_processed_at")
    op.drop_column("items", "score_details")
