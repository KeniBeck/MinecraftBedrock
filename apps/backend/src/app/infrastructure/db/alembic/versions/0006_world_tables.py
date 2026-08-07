"""migración por módulo: tabla del dominio World (prefijo ``world_*``).

Fase E paso 12 — ``WorldRow`` (metadata de mundos por servidor; la fuente de
verdad del contenido es el filesystem vía ``ServerStoragePort``). Sin FKs a
otros módulos (bounded contexts, mismo criterio que Player/IAM/Configuration).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_world_tables"
down_revision: str | None = "0005_player_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea ``world_metadata`` (sufijo de módulo, §10.5)."""
    op.create_table(
        "world_metadata",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("level_name", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("activated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_world_metadata_server_id", "world_metadata", ["server_id"])


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_index("ix_world_metadata_server_id", table_name="world_metadata")
    op.drop_table("world_metadata")
