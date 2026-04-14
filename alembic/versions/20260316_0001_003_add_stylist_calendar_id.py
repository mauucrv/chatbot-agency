"""Add google_calendar_id to estilistas table

Revision ID: 003_add_stylist_calendar_id
Revises: 002_add_missing_indices
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_stylist_calendar_id'
down_revision: Union[str, None] = '002_add_missing_indices'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'estilistas',
        sa.Column('google_calendar_id', sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('estilistas', 'google_calendar_id')
