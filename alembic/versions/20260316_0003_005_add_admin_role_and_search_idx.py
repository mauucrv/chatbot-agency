"""Add rol column to admin_users and trigram search index on citas

Revision ID: 005_add_admin_role_and_search_idx
Revises: 004_add_admin_users
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "005_add_admin_role_and_search_idx"
down_revision: Union[str, None] = "004_add_admin_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type via raw SQL (more reliable than SQLAlchemy's .create())
    op.execute("DO $$ BEGIN CREATE TYPE roladmin AS ENUM ('admin', 'viewer'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    # Add role column with default 'admin'
    op.execute(
        "ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS rol roladmin DEFAULT 'admin' NOT NULL"
    )

    # Enable pg_trgm extension for trigram search (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # GIN trigram index for fast ILIKE on nombre_cliente
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_citas_nombre_cliente_trgm "
        "ON citas USING gin (nombre_cliente gin_trgm_ops)"
    )

    # GIN trigram index for fast ILIKE on telefono_cliente
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_citas_telefono_cliente_trgm "
        "ON citas USING gin (telefono_cliente gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_citas_telefono_cliente_trgm")
    op.execute("DROP INDEX IF EXISTS ix_citas_nombre_cliente_trgm")
    op.drop_column("admin_users", "rol")
    op.execute("DROP TYPE IF EXISTS roladmin")
