"""Add missing indices for citas table

Revision ID: 002_add_missing_indices
Revises: 001_initial_migration
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_missing_indices'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add index on citas.inicio for date-based queries
    op.create_index('ix_citas_inicio', 'citas', ['inicio'], if_not_exists=True)

    # Add index on citas.estado for status-based filtering
    op.create_index('ix_citas_estado', 'citas', ['estado'], if_not_exists=True)

    # Add index on citas.estilista_id for stylist lookups
    op.create_index('ix_citas_estilista_id', 'citas', ['estilista_id'], if_not_exists=True)

    # Add explicit index on citas.id_evento_google (unique constraint may not create index on all DBs)
    op.create_index('ix_citas_id_evento_google', 'citas', ['id_evento_google'], unique=True, if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_citas_id_evento_google', table_name='citas', if_exists=True)
    op.drop_index('ix_citas_estilista_id', table_name='citas', if_exists=True)
    op.drop_index('ix_citas_estado', table_name='citas', if_exists=True)
    op.drop_index('ix_citas_inicio', table_name='citas', if_exists=True)
