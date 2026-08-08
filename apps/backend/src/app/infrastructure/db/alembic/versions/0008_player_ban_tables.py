"""migración por módulo: tablas de bans del dominio Player (prefijo ``player_*``).

Sistema de bans persistido (ADR-011): ``player_global_bans`` (ban de
panel-wide, agregado ``GlobalBan``) y ``player_server_bans`` (ban por
servidor, agregado ``ServerBan``). Unicidad sobre el gamertag normalizado
(lower-case) para evitar duplicados e índices por ``xuid`` cuando no sea null.
Sin FKs a otros módulos (bounded contexts, mismo criterio que World/Backup).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_player_ban_tables"
down_revision: str | None = "0007_backup_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea ``player_global_bans`` y ``player_server_bans`` con sus índices."""
    op.create_table(
        "player_global_bans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("xuid", sa.String(length=64), nullable=True),
        sa.Column("gamertag", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("banned_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "player_server_bans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("xuid", sa.String(length=64), nullable=True),
        sa.Column("gamertag", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("banned_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_player_global_bans_gamertag",
        "player_global_bans",
        [sa.text("lower(gamertag)")],
        unique=True,
    )
    op.create_index("ix_player_global_bans_xuid", "player_global_bans", ["xuid"])
    op.create_index(
        "uq_player_server_bans_server_gamertag",
        "player_server_bans",
        ["server_id", sa.text("lower(gamertag)")],
        unique=True,
    )
    op.create_index(
        "ix_player_server_bans_server_xuid",
        "player_server_bans",
        ["server_id", "xuid"],
    )


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_index("ix_player_server_bans_server_xuid", table_name="player_server_bans")
    op.drop_index("uq_player_server_bans_server_gamertag", table_name="player_server_bans")
    op.drop_index("ix_player_global_bans_xuid", table_name="player_global_bans")
    op.drop_index("uq_player_global_bans_gamertag", table_name="player_global_bans")
    op.drop_table("player_server_bans")
    op.drop_table("player_global_bans")
