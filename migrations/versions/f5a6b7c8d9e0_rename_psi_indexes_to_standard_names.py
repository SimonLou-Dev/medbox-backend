"""rename_psi_indexes_to_standard_names

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-04-04 08:49:46.727643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = "prescription_schedule_items"
_RENAMES = [
    ("ix_psi_box_id",          "ix_prescription_schedule_items_box_id"),
    ("ix_psi_prescription_id", "ix_prescription_schedule_items_prescription_id"),
    ("ix_psi_scheduled_at",    "ix_prescription_schedule_items_scheduled_at"),
    ("ix_psi_status",          "ix_prescription_schedule_items_status"),
    ("ix_psi_tenant_id",       "ix_prescription_schedule_items_tenant_id"),
]


def upgrade() -> None:
    for old, new in _RENAMES:
        op.execute(f'ALTER INDEX "{old}" RENAME TO "{new}"')


def downgrade() -> None:
    for old, new in _RENAMES:
        op.execute(f'ALTER INDEX "{new}" RENAME TO "{old}"')
