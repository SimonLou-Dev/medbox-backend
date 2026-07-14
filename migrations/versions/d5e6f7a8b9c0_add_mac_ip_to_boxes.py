"""add mac_address and ip_address to boxes

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-14 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "boxes",
        sa.Column("mac_address", sa.String(length=17), nullable=True),
    )
    op.add_column(
        "boxes",
        sa.Column("ip_address", sa.String(length=45), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("boxes", "ip_address")
    op.drop_column("boxes", "mac_address")
