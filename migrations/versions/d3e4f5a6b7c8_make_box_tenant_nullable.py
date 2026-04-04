"""make box tenant_id nullable for unassigned boxes

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-04-04 01:00:00.000000

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("boxes", "tenant_id", nullable=True)
    op.drop_constraint("boxes_tenant_id_fkey", "boxes", type_="foreignkey")
    op.create_foreign_key(
        "boxes_tenant_id_fkey",
        "boxes", "tenants",
        ["tenant_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("boxes_tenant_id_fkey", "boxes", type_="foreignkey")
    op.create_foreign_key(
        "boxes_tenant_id_fkey",
        "boxes", "tenants",
        ["tenant_id"], ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("boxes", "tenant_id", nullable=False)
