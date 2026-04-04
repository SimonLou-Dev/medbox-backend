"""remove battery and software_version from boxes

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-04 00:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("boxes", "battery_level")
    op.drop_column("boxes", "on_battery")
    op.drop_column("boxes", "software_version")


def downgrade() -> None:
    op.add_column("boxes", sa.Column("software_version", sa.String(50), nullable=True))
    op.add_column("boxes", sa.Column("on_battery", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("boxes", sa.Column("battery_level", sa.Integer(), nullable=True))
