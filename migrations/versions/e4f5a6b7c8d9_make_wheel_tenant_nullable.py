"""make wheel tenant_id nullable for unassigned wheels

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-04-04 02:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("wheels", "tenant_id", nullable=True)
    op.drop_constraint("wheels_tenant_id_fkey", "wheels", type_="foreignkey")
    op.create_foreign_key(
        "wheels_tenant_id_fkey",
        "wheels", "tenants",
        ["tenant_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("wheels_tenant_id_fkey", "wheels", type_="foreignkey")
    op.create_foreign_key(
        "wheels_tenant_id_fkey",
        "wheels", "tenants",
        ["tenant_id"], ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("wheels", "tenant_id", nullable=False)
