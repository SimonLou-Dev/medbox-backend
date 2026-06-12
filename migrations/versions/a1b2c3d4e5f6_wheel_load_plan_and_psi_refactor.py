"""wheel_load_plan_and_psi_refactor

Revision ID: a1b2c3d4e5f6
Revises: f5a6b7c8d9e0
Create Date: 2026-06-12 00:00:00.000000

Remplace prescription_item_id (singulier) et prescription_id sur
PrescriptionScheduleItem par wheel_slot_id + wheel_load_plan_id.
Crée les tables wheel_load_plans et wheel_load_plan_prescriptions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- wheel_load_plans ---
    op.create_table(
        "wheel_load_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("wheel_id", sa.UUID(), nullable=False),
        sa.Column("box_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["box_id"], ["boxes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wheel_id"], ["wheels.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wheel_load_plans_tenant_id", "wheel_load_plans", ["tenant_id"]
    )
    op.create_index(
        "ix_wheel_load_plans_wheel_id", "wheel_load_plans", ["wheel_id"]
    )
    op.create_index(
        "ix_wheel_load_plans_box_id", "wheel_load_plans", ["box_id"]
    )
    op.create_index(
        "ix_wheel_load_plans_status", "wheel_load_plans", ["status"]
    )

    # --- wheel_load_plan_prescriptions ---
    op.create_table(
        "wheel_load_plan_prescriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("prescription_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["wheel_load_plans.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["prescription_id"], ["prescriptions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wlp_prescriptions_plan_id",
        "wheel_load_plan_prescriptions",
        ["plan_id"],
    )
    op.create_index(
        "ix_wlp_prescriptions_prescription_id",
        "wheel_load_plan_prescriptions",
        ["prescription_id"],
    )

    # --- prescription_schedule_items : suppression anciens champs ---
    op.drop_index(
        "ix_prescription_schedule_items_prescription_id",
        table_name="prescription_schedule_items",
        if_exists=True,
    )
    op.drop_column("prescription_schedule_items", "prescription_id")
    op.drop_column("prescription_schedule_items", "prescription_item_id")
    op.drop_column("prescription_schedule_items", "dispatched_at")

    # --- prescription_schedule_items : ajout nouveaux champs ---
    op.add_column(
        "prescription_schedule_items",
        sa.Column(
            "wheel_load_plan_id",
            sa.UUID(),
            sa.ForeignKey("wheel_load_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "prescription_schedule_items",
        sa.Column(
            "wheel_slot_id",
            sa.UUID(),
            sa.ForeignKey("wheel_slots.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_psi_wheel_load_plan_id",
        "prescription_schedule_items",
        ["wheel_load_plan_id"],
    )
    op.create_index(
        "ix_psi_wheel_slot_id",
        "prescription_schedule_items",
        ["wheel_slot_id"],
    )


def downgrade() -> None:
    # prescription_schedule_items : restauration anciens champs
    op.drop_index("ix_psi_wheel_slot_id", table_name="prescription_schedule_items")
    op.drop_index(
        "ix_psi_wheel_load_plan_id", table_name="prescription_schedule_items"
    )
    op.drop_column("prescription_schedule_items", "wheel_slot_id")
    op.drop_column("prescription_schedule_items", "wheel_load_plan_id")

    op.add_column(
        "prescription_schedule_items",
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "prescription_schedule_items",
        sa.Column("prescription_item_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "prescription_schedule_items",
        sa.Column("prescription_id", sa.UUID(), nullable=False),
    )
    op.create_index(
        "ix_prescription_schedule_items_prescription_id",
        "prescription_schedule_items",
        ["prescription_id"],
    )

    # suppression nouvelles tables
    op.drop_index(
        "ix_wlp_prescriptions_prescription_id",
        table_name="wheel_load_plan_prescriptions",
    )
    op.drop_index(
        "ix_wlp_prescriptions_plan_id", table_name="wheel_load_plan_prescriptions"
    )
    op.drop_table("wheel_load_plan_prescriptions")

    op.drop_index("ix_wheel_load_plans_status", table_name="wheel_load_plans")
    op.drop_index("ix_wheel_load_plans_box_id", table_name="wheel_load_plans")
    op.drop_index("ix_wheel_load_plans_wheel_id", table_name="wheel_load_plans")
    op.drop_index("ix_wheel_load_plans_tenant_id", table_name="wheel_load_plans")
    op.drop_table("wheel_load_plans")
