"""merge heads

Revision ID: 9da7efe0d95d
Revises: b2f4e6a8c0d1, ff252ce435c9
Create Date: 2026-02-15 22:26:44.805110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9da7efe0d95d'
down_revision: Union[str, None] = ('b2f4e6a8c0d1', 'ff252ce435c9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
