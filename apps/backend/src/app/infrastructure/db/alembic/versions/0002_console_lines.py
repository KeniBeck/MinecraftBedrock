"""migración por módulo: tablas del dominio Console (prefijo ``console_*``).

Fase A paso 2 — buffer de consola persistido (líneas + seq por servidor).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_console_lines"
down_revision: str | None = "0001_server_servers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea la tabla ``console_lines`` (sufijo de tabla por módulo, §10.5)."""
    op.create_table(
        "console_lines",
        sa.Column("server_id", sa.String(length=36), primary_key=True),
        sa.Column("seq", sa.Integer(), primary_key=True),
        sa.Column("line", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_table("console_lines")
