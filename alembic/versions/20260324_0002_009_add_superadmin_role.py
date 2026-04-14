"""Add superadmin role to roladmin enum

Revision ID: 009_add_superadmin_role
Revises: 008_add_multi_tenant
Create Date: 2026-03-24

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "009_add_superadmin_role"
down_revision: Union[str, None] = "008_add_multi_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE roladmin ADD VALUE IF NOT EXISTS 'superadmin' BEFORE 'admin'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # A full enum recreation would be needed, but this is rarely worth the risk.
    pass
