"""migración por módulo: tablas del dominio Player (prefijo ``player_*``).

Fase E paso 11 — ``PlayerRow`` (caché de identidad XUID + playtime) y
``PlaySessionRow`` (presencia por servidor). Sin FKs a otros módulos
(bounded contexts, mismo criterio que IAM/Configuration).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_player_tables"
down_revision: str | None = "0004_configuration_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea ``player_players`` y ``player_sessions`` (sufijo de módulo, §10.5)."""
    op.create_table(
        "player_players",
        sa.Column("xuid", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("playtime_seconds", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "player_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("xuid", sa.String(length=64), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(length=16), nullable=True),
        sa.Column("playtime_seconds", sa.BigInteger(), nullable=False),
    )
    op.create_index("ix_player_sessions_server_id", "player_sessions", ["server_id"])
    op.create_index("ix_player_sessions_xuid", "player_sessions", ["xuid"])


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_index("ix_player_sessions_xuid", table_name="player_sessions")
    op.drop_index("ix_player_sessions_server_id", table_name="player_sessions")
    op.drop_table("player_sessions")
    op.drop_table("player_players")
