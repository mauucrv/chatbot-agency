"""Add multi-tenant support: tenants table + tenant_id FK on all tables

Revision ID: 008_add_multi_tenant
Revises: 007_add_leads
Create Date: 2026-03-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "008_add_multi_tenant"
down_revision: Union[str, None] = "007_add_leads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, table_name: str) -> bool:
    result = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :t)"
    ), {"t": table_name})
    return result.scalar()


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    result = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c)"
    ), {"t": table_name, "c": column_name})
    return result.scalar()


def _constraint_exists(bind, constraint_name: str) -> bool:
    result = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.table_constraints "
        "WHERE constraint_schema = 'public' AND constraint_name = :c)"
    ), {"c": constraint_name})
    return result.scalar()


def _index_exists(bind, index_name: str) -> bool:
    result = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_indexes "
        "WHERE schemaname = 'public' AND indexname = :i)"
    ), {"i": index_name})
    return result.scalar()


def upgrade() -> None:
    bind = op.get_bind()

    # 0. Create enum type idempotently (handles partial previous runs)
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE plantenant AS ENUM ('trial', 'active', 'suspended'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; "
        "END $$;"
    )

    # 1. Create tenants table (if not already created by create_all fallback)
    if not _table_exists(bind, "tenants"):
        op.create_table(
            "tenants",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("nombre", sa.String(200), nullable=False),
            sa.Column("slug", sa.String(100), nullable=False),
            sa.Column(
                "plan",
                sa.Enum("trial", "active", "suspended", name="plantenant", create_type=False),
                server_default="trial",
                nullable=False,
            ),
            sa.Column("chatwoot_account_id", sa.Integer(), nullable=True),
            sa.Column("chatwoot_inbox_id", sa.Integer(), nullable=True),
            sa.Column("chatwoot_api_token", sa.String(255), nullable=True),
            sa.Column("webhook_token", sa.String(255), nullable=True),
            sa.Column("google_calendar_id", sa.String(255), nullable=True),
            sa.Column("owner_phone", sa.String(20), nullable=True),
            sa.Column("owner_email", sa.String(150), nullable=True),
            sa.Column("system_prompt_override", sa.Text(), nullable=True),
            sa.Column("max_conversations_per_day", sa.Integer(), server_default="100", nullable=False),
            sa.Column("timezone", sa.String(50), server_default="America/Mexico_City", nullable=False),
            sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists(bind, "ix_tenants_slug"):
        op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # 2. Insert default tenant for existing data (if not already present)
    result = bind.execute(sa.text("SELECT COUNT(*) FROM tenants WHERE id = 1"))
    if result.scalar() == 0:
        op.execute(
            "INSERT INTO tenants (id, nombre, slug, plan, max_conversations_per_day, timezone, activo) "
            "VALUES (1, 'AgencyBot', 'agencybot', 'active', 100, 'America/Mexico_City', true)"
        )

    # 3. Add tenant_id FK to all tables (idempotent per-column)
    tables_needing_tenant_id = [
        "servicios_belleza",
        "estilistas",
        "citas",
        "informacion_general",
        "conversaciones_chatwoot",
        "keywords_humano",
        "admin_users",
        "estadisticas_bot",
        "leads",
        "fichas_clientes",
        "productos",
        "ventas",
    ]

    for table in tables_needing_tenant_id:
        if not _column_exists(bind, table, "tenant_id"):
            op.add_column(
                table,
                sa.Column("tenant_id", sa.Integer(), nullable=True),
            )
            op.execute(f"UPDATE {table} SET tenant_id = 1")
            op.alter_column(table, "tenant_id", nullable=False)

        if not _constraint_exists(bind, f"fk_{table}_tenant_id"):
            op.create_foreign_key(
                f"fk_{table}_tenant_id",
                table,
                "tenants",
                ["tenant_id"],
                ["id"],
                ondelete="CASCADE",
            )

        if not _index_exists(bind, f"ix_{table}_tenant_id"):
            op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])

    # 4. Remove single-column unique constraints that need to become per-tenant
    if _constraint_exists(bind, "servicios_belleza_servicio_key"):
        op.drop_constraint("servicios_belleza_servicio_key", "servicios_belleza", type_="unique")

    if _constraint_exists(bind, "keywords_humano_keyword_key"):
        op.drop_constraint("keywords_humano_keyword_key", "keywords_humano", type_="unique")

    if _constraint_exists(bind, "admin_users_username_key"):
        op.drop_constraint("admin_users_username_key", "admin_users", type_="unique")

    if not _constraint_exists(bind, "uq_admin_users_tenant_username"):
        op.create_unique_constraint(
            "uq_admin_users_tenant_username", "admin_users", ["tenant_id", "username"]
        )

    if _constraint_exists(bind, "fichas_clientes_telefono_key"):
        op.drop_constraint("fichas_clientes_telefono_key", "fichas_clientes", type_="unique")

    if _constraint_exists(bind, "conversaciones_chatwoot_chatwoot_conversation_id_key"):
        op.drop_constraint(
            "conversaciones_chatwoot_chatwoot_conversation_id_key",
            "conversaciones_chatwoot",
            type_="unique",
        )


def downgrade() -> None:
    # Restore unique constraints
    op.create_unique_constraint(
        "conversaciones_chatwoot_chatwoot_conversation_id_key",
        "conversaciones_chatwoot",
        ["chatwoot_conversation_id"],
    )
    op.create_unique_constraint(
        "fichas_clientes_telefono_key", "fichas_clientes", ["telefono"]
    )
    op.drop_constraint("uq_admin_users_tenant_username", "admin_users", type_="unique")
    op.create_unique_constraint(
        "admin_users_username_key", "admin_users", ["username"]
    )
    op.create_unique_constraint(
        "keywords_humano_keyword_key", "keywords_humano", ["keyword"]
    )
    op.create_unique_constraint(
        "servicios_belleza_servicio_key", "servicios_belleza", ["servicio"]
    )

    # Remove tenant_id from all tables
    tables = [
        "ventas", "productos", "fichas_clientes", "leads",
        "estadisticas_bot", "admin_users", "keywords_humano",
        "conversaciones_chatwoot", "informacion_general", "citas",
        "estilistas", "servicios_belleza",
    ]
    for table in tables:
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table)
        op.drop_column(table, "tenant_id")

    # Drop tenants table
    op.drop_index("ix_tenants_slug", "tenants")
    op.drop_table("tenants")
    op.execute("DROP TYPE IF EXISTS plantenant")
