"""add last_sync_at to boxes

Revision ID: b1c2d3e4f5a6
Revises: a3f1b2c4d5e6
Create Date: 2026-04-03 21:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a3f1b2c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "boxes",
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("boxes", "last_sync_at")
