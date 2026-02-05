"""add unique constraint on keycloak_subject

Revision ID: 7f8e9d1c2b3a
Revises: 4a2c3b1d5e7f
Create Date: 2026-02-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f8e9d1c2b3a'
down_revision: Union[str, None] = '4a2c3b1d5e7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Supprimer les doublons en gardant l'utilisateur avec tenant_id (s'il existe)
    # ou le plus ancien si aucun n'a de tenant
    op.execute("""
        DELETE FROM users
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                    ROW_NUMBER() OVER (
                        PARTITION BY keycloak_subject
                        ORDER BY
                            CASE WHEN tenant_id IS NOT NULL THEN 0 ELSE 1 END,
                            created_at ASC
                    ) as rn
                FROM users
            ) duplicates
            WHERE rn > 1
        )
    """)

    # Ajouter la contrainte unique
    op.create_unique_constraint('uq_users_keycloak_subject', 'users', ['keycloak_subject'])


def downgrade() -> None:
    op.drop_constraint('uq_users_keycloak_subject', 'users', type_='unique')
