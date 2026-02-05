"""add sended_by_user_id to invitations

Revision ID: 8a9b0c1d2e3f
Revises: 7f8e9d1c2b3a
Create Date: 2026-02-05 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a9b0c1d2e3f'
down_revision: Union[str, None] = '7f8e9d1c2b3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ajouter la colonne sended_by_user_id (nullable pour les invitations existantes)
    op.add_column(
        'invitations',
        sa.Column('sended_by_user_id', sa.Uuid(), nullable=True)
    )

    # Ajouter la foreign key
    op.create_foreign_key(
        'fk_invitations_sended_by_user_id',
        'invitations',
        'users',
        ['sended_by_user_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_invitations_sended_by_user_id', 'invitations', type_='foreignkey')
    op.drop_column('invitations', 'sended_by_user_id')
