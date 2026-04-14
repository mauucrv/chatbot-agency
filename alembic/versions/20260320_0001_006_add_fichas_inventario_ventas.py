"""Add fichas_clientes, productos, movimientos_inventario, ventas, detalles_venta

Revision ID: 006_add_fichas_inventario_ventas
Revises: 005_add_admin_role_and_search_idx
Create Date: 2026-03-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "006_add_fichas_inventario_ventas"
down_revision: Union[str, None] = "005_add_admin_role_and_search_idx"
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
    # ── Enum types (idempotent) ───────────────────────────
    op.execute(
        "DO $$ BEGIN CREATE TYPE tipocabello AS ENUM "
        "('liso','ondulado','rizado','crespo','mixto'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE tipopiel AS ENUM "
        "('normal','seca','grasa','mixta','sensible'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE categoriaproducto AS ENUM "
        "('reventa','uso_salon'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE tipomovimiento AS ENUM "
        "('entrada','salida','ajuste'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE metodopago AS ENUM "
        "('efectivo','tarjeta','transferencia','otro'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN CREATE TYPE tipoventa AS ENUM "
        "('producto','servicio','mixta'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    # Use postgresql.ENUM with create_type=False so SQLAlchemy never
    # tries to CREATE TYPE again during create_table (asyncpg bug).
    e_cabello = postgresql.ENUM('liso', 'ondulado', 'rizado', 'crespo', 'mixto', name='tipocabello', create_type=False)
    e_piel = postgresql.ENUM('normal', 'seca', 'grasa', 'mixta', 'sensible', name='tipopiel', create_type=False)
    e_categoria = postgresql.ENUM('reventa', 'uso_salon', name='categoriaproducto', create_type=False)
    e_movimiento = postgresql.ENUM('entrada', 'salida', 'ajuste', name='tipomovimiento', create_type=False)
    e_metodo = postgresql.ENUM('efectivo', 'tarjeta', 'transferencia', 'otro', name='metodopago', create_type=False)
    e_tipoventa = postgresql.ENUM('producto', 'servicio', 'mixta', name='tipoventa', create_type=False)

    # ── fichas_clientes ─────────────────────────────────────
    if not _table_exists("fichas_clientes"):
        op.create_table(
            "fichas_clientes",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("nombre", sa.String(100), nullable=False),
            sa.Column("telefono", sa.String(20), nullable=False, unique=True),
            sa.Column("email", sa.String(150), nullable=True),
            sa.Column("tipo_cabello", e_cabello, nullable=True),
            sa.Column("tipo_piel", e_piel, nullable=True),
            sa.Column("alergias", sa.Text, nullable=True),
            sa.Column("historial_color", sa.JSON, nullable=True, default=[]),
            sa.Column("historial_tratamientos", sa.JSON, nullable=True, default=[]),
            sa.Column("preferencias", sa.Text, nullable=True),
            sa.Column("notas", sa.Text, nullable=True),
            sa.Column("activo", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_fichas_clientes_telefono", "fichas_clientes", ["telefono"])

    # ── productos ───────────────────────────────────────────
    if not _table_exists("productos"):
        op.create_table(
            "productos",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("nombre", sa.String(150), nullable=False),
            sa.Column("marca", sa.String(100), nullable=True),
            sa.Column("categoria", e_categoria, nullable=False),
            sa.Column("subcategoria", sa.String(100), nullable=True),
            sa.Column("cantidad", sa.Integer, default=0, nullable=False),
            sa.Column("unidad", sa.String(30), nullable=True, default="unidad"),
            sa.Column("costo_unitario", sa.Float, default=0.0, nullable=False),
            sa.Column("precio_venta", sa.Float, nullable=True),
            sa.Column("stock_minimo", sa.Integer, default=5, nullable=False),
            sa.Column("fecha_vencimiento", sa.DateTime(timezone=True), nullable=True),
            sa.Column("codigo_barras", sa.String(50), nullable=True),
            sa.Column("activo", sa.Boolean, default=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_productos_nombre", "productos", ["nombre"])
        op.create_index("ix_productos_codigo_barras", "productos", ["codigo_barras"])

    # ── movimientos_inventario ──────────────────────────────
    if not _table_exists("movimientos_inventario"):
        op.create_table(
            "movimientos_inventario",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("producto_id", sa.Integer, sa.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tipo", e_movimiento, nullable=False),
            sa.Column("cantidad", sa.Integer, nullable=False),
            sa.Column("cantidad_anterior", sa.Integer, nullable=False),
            sa.Column("cantidad_nueva", sa.Integer, nullable=False),
            sa.Column("motivo", sa.String(255), nullable=True),
            sa.Column("referencia", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_movimientos_inventario_producto_id", "movimientos_inventario", ["producto_id"])

    # ── ventas ──────────────────────────────────────────────
    if not _table_exists("ventas"):
        op.create_table(
            "ventas",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("ficha_cliente_id", sa.Integer, sa.ForeignKey("fichas_clientes.id", ondelete="SET NULL"), nullable=True),
            sa.Column("cita_id", sa.Integer, sa.ForeignKey("citas.id", ondelete="SET NULL"), nullable=True),
            sa.Column("tipo", e_tipoventa, nullable=False),
            sa.Column("subtotal", sa.Float, nullable=False),
            sa.Column("descuento", sa.Float, default=0.0),
            sa.Column("total", sa.Float, nullable=False),
            sa.Column("metodo_pago", e_metodo, default="efectivo"),
            sa.Column("notas", sa.Text, nullable=True),
            sa.Column("vendedor", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_ventas_ficha_cliente_id", "ventas", ["ficha_cliente_id"])
        op.create_index("ix_ventas_cita_id", "ventas", ["cita_id"])
        op.create_index("ix_ventas_created_at", "ventas", ["created_at"])

    # ── detalles_venta ──────────────────────────────────────
    if not _table_exists("detalles_venta"):
        op.create_table(
            "detalles_venta",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("venta_id", sa.Integer, sa.ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False),
            sa.Column("producto_id", sa.Integer, sa.ForeignKey("productos.id", ondelete="SET NULL"), nullable=True),
            sa.Column("descripcion", sa.String(200), nullable=False),
            sa.Column("cantidad", sa.Integer, default=1, nullable=False),
            sa.Column("precio_unitario", sa.Float, nullable=False),
            sa.Column("subtotal", sa.Float, nullable=False),
        )
        op.create_index("ix_detalles_venta_venta_id", "detalles_venta", ["venta_id"])
        op.create_index("ix_detalles_venta_producto_id", "detalles_venta", ["producto_id"])

    # ── GIN trigram indexes for search (idempotent) ────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_fichas_clientes_nombre_trgm "
        "ON fichas_clientes USING gin (nombre gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_fichas_clientes_telefono_trgm "
        "ON fichas_clientes USING gin (telefono gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_productos_nombre_trgm "
        "ON productos USING gin (nombre gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_productos_nombre_trgm")
    op.execute("DROP INDEX IF EXISTS ix_fichas_clientes_telefono_trgm")
    op.execute("DROP INDEX IF EXISTS ix_fichas_clientes_nombre_trgm")

    op.drop_table("detalles_venta")
    op.drop_table("ventas")
    op.drop_table("movimientos_inventario")
    op.drop_table("productos")
    op.drop_table("fichas_clientes")

    op.execute("DROP TYPE IF EXISTS tipoventa")
    op.execute("DROP TYPE IF EXISTS metodopago")
    op.execute("DROP TYPE IF EXISTS tipomovimiento")
    op.execute("DROP TYPE IF EXISTS categoriaproducto")
    op.execute("DROP TYPE IF EXISTS tipopiel")
    op.execute("DROP TYPE IF EXISTS tipocabello")
