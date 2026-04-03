"""add prescription_schedule_items

Revision ID: a3f1b2c4d5e6
Revises: 9da7efe0d95d
Create Date: 2026-04-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f1b2c4d5e6"
down_revision: Union[str, None] = "9da7efe0d95d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prescription_schedule_items",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("prescription_id", sa.Uuid(), nullable=False),
        sa.Column("prescription_item_id", sa.Uuid(), nullable=True),
        sa.Column("box_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_reason", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["box_id"], ["boxes.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["prescription_id"], ["prescriptions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["prescription_item_id"], ["prescription_items.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_psi_tenant_id", "prescription_schedule_items", ["tenant_id"]
    )
    op.create_index(
        "ix_psi_prescription_id", "prescription_schedule_items", ["prescription_id"]
    )
    op.create_index(
        "ix_psi_box_id", "prescription_schedule_items", ["box_id"]
    )
    op.create_index(
        "ix_psi_scheduled_at", "prescription_schedule_items", ["scheduled_at"]
    )
    op.create_index(
        "ix_psi_status", "prescription_schedule_items", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_psi_status", table_name="prescription_schedule_items")
    op.drop_index("ix_psi_scheduled_at", table_name="prescription_schedule_items")
    op.drop_index("ix_psi_box_id", table_name="prescription_schedule_items")
    op.drop_index("ix_psi_prescription_id", table_name="prescription_schedule_items")
    op.drop_index("ix_psi_tenant_id", table_name="prescription_schedule_items")
    op.drop_table("prescription_schedule_items")
