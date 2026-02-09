"""make invitation email nullable

Revision ID: b2f4e6a8c0d1
Revises: a125b3012484
Create Date: 2026-02-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f4e6a8c0d1'
down_revision: Union[str, None] = 'a125b3012484'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'invitations',
        'email',
        existing_type=sa.String(320),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'invitations',
        'email',
        existing_type=sa.String(320),
        nullable=False,
    )
