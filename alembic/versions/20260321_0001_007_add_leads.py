"""Add leads table for CRM

Revision ID: 007_add_leads
Revises: 006_add_fichas_inventario_ventas
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "007_add_leads"
down_revision: Union[str, None] = "006_add_fichas_inventario_ventas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = :name)"
    ), {"name": name})
    return result.scalar()


def upgrade() -> None:
    # Create enum types (idempotent)
    conn = op.get_bind()
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE etapalead AS ENUM (
                'nuevo', 'contactado', 'cita_agendada',
                'en_negociacion', 'cerrado_ganado', 'cerrado_perdido'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE origenlead AS ENUM (
                'whatsapp_organico', 'meta_ads', 'referido', 'sitio_web', 'otro'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """))

    if not _table_exists("leads"):
        op.create_table(
            "leads",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("nombre", sa.String(100), nullable=True),
            sa.Column("telefono", sa.String(20), nullable=False),
            sa.Column("email", sa.String(150), nullable=True),
            sa.Column("empresa", sa.String(150), nullable=True),
            sa.Column(
                "etapa",
                sa.Enum("nuevo", "contactado", "cita_agendada", "en_negociacion",
                        "cerrado_ganado", "cerrado_perdido",
                        name="etapalead", create_type=False),
                nullable=False,
                server_default="nuevo",
            ),
            sa.Column(
                "origen",
                sa.Enum("whatsapp_organico", "meta_ads", "referido", "sitio_web", "otro",
                        name="origenlead", create_type=False),
                nullable=False,
                server_default="whatsapp_organico",
            ),
            sa.Column("notas", sa.Text(), nullable=True),
            sa.Column("valor_estimado", sa.Float(), nullable=True),
            sa.Column("servicio_interes", sa.String(200), nullable=True),
            sa.Column("chatwoot_conversation_id", sa.Integer(), nullable=True),
            sa.Column("chatwoot_contact_id", sa.Integer(), nullable=True),
            sa.Column("ultimo_contacto", sa.DateTime(timezone=True), nullable=True),
            sa.Column("proximo_seguimiento", sa.DateTime(timezone=True), nullable=True),
            sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_leads_telefono", "leads", ["telefono"])
        op.create_index("ix_leads_etapa", "leads", ["etapa"])
        op.create_index("ix_leads_chatwoot_conversation_id", "leads", ["chatwoot_conversation_id"])

        # GIN trigram index for ILIKE search on nombre
        conn.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_leads_nombre_trgm ON leads "
            "USING gin (nombre gin_trgm_ops)"
        ))


def downgrade() -> None:
    op.drop_table("leads")
    op.execute("DROP TYPE IF EXISTS etapalead")
    op.execute("DROP TYPE IF EXISTS origenlead")
