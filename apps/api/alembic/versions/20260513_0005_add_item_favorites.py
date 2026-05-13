"""add item favorites

Revision ID: 20260513_0005
Revises: 20260512_0004
Create Date: 2026-05-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260513_0005"
down_revision: str | None = "20260512_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("items", sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("items", "is_favorite", server_default=None)
    op.create_index(op.f("ix_items_is_favorite"), "items", ["is_favorite"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_items_is_favorite"), table_name="items")
    op.drop_column("items", "is_favorite")
