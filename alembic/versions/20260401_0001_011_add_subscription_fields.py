"""Add subscription billing fields to tenants

Revision ID: 011_add_subscription_fields
Revises: 010_add_info_created_at
Create Date: 2026-04-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "011_add_subscription_fields"
down_revision: Union[str, None] = "010_add_info_created_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("last_payment_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("payment_notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "payment_notes")
    op.drop_column("tenants", "last_payment_at")
    op.drop_column("tenants", "subscription_expires_at")
