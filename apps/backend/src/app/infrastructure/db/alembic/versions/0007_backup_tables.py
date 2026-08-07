"""migración por módulo: tabla del dominio Backup (prefijo ``backup_*``).

Fase F paso 13 — ``BackupRow`` (metadata de artefactos de backup; el contenido
vive en el ``BackupStorePort``, ``storage_ref`` es opaco). Sin FKs a otros
módulos (bounded contexts, mismo criterio que World/Player).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_backup_tables"
down_revision: str | None = "0006_world_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea ``backup_backups`` (sufijo de módulo, §10.5)."""
    op.create_table(
        "backup_backups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("world_name", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("storage_ref", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("entries", sa.JSON(), nullable=False),
        sa.Column("duration_seconds", sa.BigInteger(), nullable=True),
        sa.Column("protected", sa.Boolean(), nullable=False),
        sa.Column("orphaned", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_backup_backups_server_id", "backup_backups", ["server_id"])


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_index("ix_backup_backups_server_id", table_name="backup_backups")
    op.drop_table("backup_backups")
