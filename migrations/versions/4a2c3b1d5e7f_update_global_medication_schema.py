"""update global_medication schema from French API

Revision ID: 4a2c3b1d5e7f
Revises: 56b761bc6dba
Create Date: 2026-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a2c3b1d5e7f'
down_revision: Union[str, None] = '56b761bc6dba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, drop dependent foreign key constraints
    op.drop_constraint('prescription_items_medication_id_fkey', 'prescription_items', type_='foreignkey')
    
    # Drop the old global_medications table
    op.drop_table('global_medications')
    
    # Create new global_medications table with French API schema (CIS as primary key)
    op.create_table('global_medications',
        sa.Column('cis', sa.Integer(), nullable=False, comment='CIS Code from French BDPM API'),
        sa.Column('element_pharmaceutique', sa.String(length=255), nullable=False),
        sa.Column('forme_pharmaceutique', sa.String(length=128), nullable=False),
        sa.Column('voies_administration', sa.JSON(), nullable=True, comment='Array of administration routes'),
        sa.Column('status_autorisation', sa.String(length=128), nullable=False),
        sa.Column('type_procedure', sa.String(length=128), nullable=False),
        sa.Column('etat_commercialisation', sa.String(length=128), nullable=False),
        sa.Column('date_amm', sa.Date(), nullable=True),
        sa.Column('titulaire', sa.String(length=255), nullable=False),
        sa.Column('sync_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('cis'),
        sa.Index('idx_global_medications_element_pharmaceutique', 'element_pharmaceutique'),
        sa.Index('idx_global_medications_titulaire', 'titulaire'),
    )
    
    # Update prescription_items table: change medication_id from UUID to INTEGER (cis)
    op.alter_column('prescription_items', 'medication_id', 
                    existing_type=sa.Uuid(),
                    type_=sa.Integer(),
                    nullable=True)
    
    # Re-add foreign key constraint with new column type
    op.create_foreign_key('prescription_items_medication_id_fkey', 
                         'prescription_items', 'global_medications',
                         ['medication_id'], ['cis'],
                         ondelete='SET NULL')


def downgrade() -> None:
    # Reverse the constraint on prescription_items
    op.drop_constraint('prescription_items_medication_id_fkey', 'prescription_items', type_='foreignkey')
    
    # Change medication_id back to UUID
    op.alter_column('prescription_items', 'medication_id',
                    existing_type=sa.Integer(),
                    type_=sa.Uuid(),
                    nullable=True)
    
    # Recreate the old global_medications table
    op.drop_table('global_medications')
    
    op.create_table('global_medications',
        sa.Column('code', sa.String(length=128), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('form', sa.String(length=128), nullable=True),
        sa.Column('brand', sa.String(length=255), nullable=True),
        sa.Column('description', sa.String(length=1024), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    
    # Re-add original foreign key
    op.create_foreign_key('prescription_items_medication_id_fkey',
                         'prescription_items', 'global_medications',
                         ['medication_id'], ['id'],
                         ondelete='SET NULL')
