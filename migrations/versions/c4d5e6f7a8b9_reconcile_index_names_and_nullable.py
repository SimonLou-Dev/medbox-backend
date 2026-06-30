"""reconcile index names and nullable columns

Aligne la DB (après a1b2c3d4e5f6) avec les modèles SQLAlchemy :
- renomme les index ix_psi_* et ix_wlp_* vers les noms auto-générés
- passe created_at/updated_at en NOT NULL sur wheel_load_plans et
  wheel_load_plan_prescriptions (TimestampMixin impose nullable=False)

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- prescription_schedule_items : renommage index ---
    op.drop_index("ix_psi_wheel_load_plan_id", table_name="prescription_schedule_items")
    op.create_index(
        "ix_prescription_schedule_items_wheel_load_plan_id",
        "prescription_schedule_items",
        ["wheel_load_plan_id"],
    )
    op.drop_index("ix_psi_wheel_slot_id", table_name="prescription_schedule_items")
    op.create_index(
        "ix_prescription_schedule_items_wheel_slot_id",
        "prescription_schedule_items",
        ["wheel_slot_id"],
    )

    # --- wheel_load_plan_prescriptions : renommage index ---
    op.drop_index("ix_wlp_prescriptions_plan_id", table_name="wheel_load_plan_prescriptions")
    op.create_index(
        "ix_wheel_load_plan_prescriptions_plan_id",
        "wheel_load_plan_prescriptions",
        ["plan_id"],
    )
    op.drop_index(
        "ix_wlp_prescriptions_prescription_id",
        table_name="wheel_load_plan_prescriptions",
    )
    op.create_index(
        "ix_wheel_load_plan_prescriptions_prescription_id",
        "wheel_load_plan_prescriptions",
        ["prescription_id"],
    )

    # --- nullable → NOT NULL (TimestampMixin) ---
    op.alter_column(
        "wheel_load_plan_prescriptions",
        "created_at",
        nullable=False,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "wheel_load_plan_prescriptions",
        "updated_at",
        nullable=False,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "wheel_load_plans",
        "created_at",
        nullable=False,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        "wheel_load_plans",
        "updated_at",
        nullable=False,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "wheel_load_plans",
        "updated_at",
        nullable=True,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "wheel_load_plans",
        "created_at",
        nullable=True,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "wheel_load_plan_prescriptions",
        "updated_at",
        nullable=True,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "wheel_load_plan_prescriptions",
        "created_at",
        nullable=True,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )

    op.drop_index(
        "ix_wheel_load_plan_prescriptions_prescription_id",
        table_name="wheel_load_plan_prescriptions",
    )
    op.create_index(
        "ix_wlp_prescriptions_prescription_id",
        "wheel_load_plan_prescriptions",
        ["prescription_id"],
    )
    op.drop_index(
        "ix_wheel_load_plan_prescriptions_plan_id",
        table_name="wheel_load_plan_prescriptions",
    )
    op.create_index(
        "ix_wlp_prescriptions_plan_id",
        "wheel_load_plan_prescriptions",
        ["plan_id"],
    )
    op.drop_index(
        "ix_prescription_schedule_items_wheel_slot_id",
        table_name="prescription_schedule_items",
    )
    op.create_index(
        "ix_psi_wheel_slot_id",
        "prescription_schedule_items",
        ["wheel_slot_id"],
    )
    op.drop_index(
        "ix_prescription_schedule_items_wheel_load_plan_id",
        table_name="prescription_schedule_items",
    )
    op.create_index(
        "ix_psi_wheel_load_plan_id",
        "prescription_schedule_items",
        ["wheel_load_plan_id"],
    )
