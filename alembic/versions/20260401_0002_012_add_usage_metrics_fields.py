"""Add usage metrics fields to estadisticas_bot

Revision ID: 012_add_usage_metrics
Revises: 011_add_subscription_fields
Create Date: 2026-04-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "012_add_usage_metrics"
down_revision: Union[str, None] = "011_add_subscription_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "estadisticas_bot",
        sa.Column("mensajes_audio", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "estadisticas_bot",
        sa.Column("mensajes_imagen", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "estadisticas_bot",
        sa.Column("usuarios_unicos", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "estadisticas_bot",
        sa.Column("tokens_openai_aprox", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("estadisticas_bot", "tokens_openai_aprox")
    op.drop_column("estadisticas_bot", "usuarios_unicos")
    op.drop_column("estadisticas_bot", "mensajes_imagen")
    op.drop_column("estadisticas_bot", "mensajes_audio")
