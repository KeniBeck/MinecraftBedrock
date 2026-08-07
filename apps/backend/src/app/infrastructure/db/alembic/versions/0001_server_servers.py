"""migración por módulo: tablas del dominio Server (prefijo ``server_*``).

Fase A paso 2 — persistencia del agregado ``Server`` (TDD §15.2).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_server_servers"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea la tabla ``server_servers`` (sufijo de tabla por módulo, §10.5)."""
    op.create_table(
        "server_servers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("image", sa.Text(), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column(
            "spec",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("runtime_id", sa.Text(), nullable=True),
        sa.Column("desired_config_rev", sa.Integer(), nullable=True),
        sa.Column("applied_config_rev", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_table("server_servers")
