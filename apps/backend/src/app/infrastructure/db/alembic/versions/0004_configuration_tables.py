"""migración por módulo: tablas del dominio Configuration (prefijo ``config_*``).

Fase D paso 10 — ``ConfigProfile`` (deseado/aplicado/versión, ADR-004) e
historial append-only ``config_history`` por servidor.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_configuration_tables"
down_revision: str | None = "0003_iam_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea ``config_profiles`` y ``config_history`` (sufijo de módulo, §10.5)."""
    op.create_table(
        "config_profiles",
        sa.Column("server_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "properties",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("config_rev", sa.Integer(), nullable=False),
        sa.Column(
            "applied",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "config_history",
        sa.Column("server_id", sa.String(length=36), primary_key=True),
        sa.Column("config_rev", sa.Integer(), primary_key=True),
        sa.Column(
            "properties",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_table("config_history")
    op.drop_table("config_profiles")
