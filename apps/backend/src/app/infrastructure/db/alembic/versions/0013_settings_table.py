"""Migración por módulo: tabla ``settings`` (Fase H paso 19).

Tabla con clave única + valor JSONB + categoría + metadatos de auditoría, y
siembra de los valores por defecto del catálogo (fuente = EnvSettingsAdapter
como base, aplicando los defaults del código).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0013_settings_table"
down_revision: str | None = "0012_iam_complete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (key, default, category, description) — catálogo de la Fase H paso 19.
_SEED: tuple[tuple[str, object, str, str], ...] = (
    (
        "storage.base_path",
        "/var/lib/bedrockpanel/data",
        "storage",
        "Ruta base para los datos de los servidores",
    ),
    (
        "storage.backup_path",
        "/var/lib/bedrockpanel/backups",
        "storage",
        "Ruta base para los backups",
    ),
    (
        "storage.template_path",
        "/var/lib/bedrockpanel/templates",
        "storage",
        "Ruta base para las plantillas",
    ),
    (
        "limits.max_servers",
        0,
        "limits",
        "Número máximo de servidores por usuario (0 = ilimitado)",
    ),
    ("limits.max_backups_per_server", 10, "limits", "Número máximo de backups por servidor"),
    ("limits.max_world_size_mb", 2048, "limits", "Tamaño máximo de mundo importado (MB)"),
    ("limits.default_cpu_cores", 2.0, "limits", "CPU por defecto para nuevos servidores"),
    ("limits.default_ram_mb", 2048, "limits", "RAM por defecto para nuevos servidores (MB)"),
    ("limits.default_disk_gb", 10, "limits", "Disco por defecto para nuevos servidores (GB)"),
    ("defaults.image", "itzg/minecraft-bedrock-server", "defaults", "Imagen Docker por defecto"),
    ("defaults.tag", "latest", "defaults", "Tag de la imagen Docker por defecto"),
    ("defaults.version", "LATEST", "defaults", "Versión BDS por defecto"),
    ("defaults.port_pool_start", 19132, "defaults", "Inicio del pool de puertos de juego"),
    ("defaults.port_pool_end", 19181, "defaults", "Fin del pool de puertos de juego"),
    ("defaults.timezone", "Etc/UTC", "defaults", "Zona horaria por defecto"),
    (
        "system.maintenance_mode",
        False,
        "system",
        "Panel en mantenimiento (bloquea operaciones)",
    ),
    ("system.log_level", "INFO", "system", "Nivel de logs por defecto"),
    ("system.audit_retention_days", 90, "system", "Días de retención del audit log"),
)


def upgrade() -> None:
    """Crea la tabla ``settings`` y la siembra con los defaults."""
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_settings_category", "settings", ["category"], unique=False)

    now = datetime.now(UTC)
    rows = [
        {
            "key": key,
            "value": value,
            "category": category,
            "description": description,
            "updated_by": "migration",
            "updated_at": now,
        }
        for key, value, category, description in _SEED
    ]
    op.bulk_insert(
        sa.table(
            "settings",
            sa.column("key", sa.String),
            sa.column("value", postgresql.JSONB),
            sa.column("category", sa.String),
            sa.column("description", sa.Text),
            sa.column("updated_by", sa.String),
            sa.column("updated_at", sa.DateTime),
        ),
        rows,
    )


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_index("ix_settings_category", table_name="settings")
    op.drop_table("settings")
