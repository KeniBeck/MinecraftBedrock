"""Migración por módulo: ajustes de mundo + permiso ``world.update``.

- ``world_metadata`` gana los ajustes opcionales por mundo (``seed``,
  ``gamemode``, ``difficulty``, ``view_distance``) que se inyectan como env al
  activar el mundo (``LEVEL_SEED``/``GAMEMODE``/``DIFFICULTY``/``VIEW_DISTANCE``).
- Permiso ``world.update`` (renombrar/ajustar mundos) para BBDD ya migradas
  (mismo patrón que ``0014_server_update_permission``): WRITE_ACTION →
  operator/admin/super_admin.
- Setting ``defaults.level_name`` = "Mi Mundo 1" (nombre del mundo por defecto
  que crea BDS en el primer arranque de un servidor nuevo).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_world_world_settings"
down_revision: str | None = "0014_server_update_permission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CODE = "world.update"
_CATEGORY = "world"
_ROLES = ("operator", "admin", "super_admin")


def upgrade() -> None:
    """Añade los ajustes por mundo, el permiso y el default de level-name."""
    op.add_column("world_metadata", sa.Column("seed", sa.String(length=64), nullable=True))
    op.add_column("world_metadata", sa.Column("gamemode", sa.String(length=32), nullable=True))
    op.add_column("world_metadata", sa.Column("difficulty", sa.String(length=32), nullable=True))
    op.add_column("world_metadata", sa.Column("view_distance", sa.Integer(), nullable=True))

    op.execute(
        f"INSERT INTO iam_permissions (code, category, description) "
        f"VALUES ('{_CODE}', '{_CATEGORY}', 'Renombrar/ajustar un mundo') "
        f"ON CONFLICT (code) DO NOTHING"
    )
    for role in _ROLES:
        op.execute(
            f"INSERT INTO iam_role_permissions (role, permission_code) "
            f"VALUES ('{role}', '{_CODE}') ON CONFLICT DO NOTHING"
        )

    now = datetime.now(UTC)
    op.bulk_insert(
        sa.table(
            "settings",
            sa.column("key", sa.String),
            sa.column("value", sa.JSON),
            sa.column("category", sa.String),
            sa.column("description", sa.Text),
            sa.column("updated_by", sa.String),
            sa.column("updated_at", sa.DateTime),
        ),
        [
            {
                "key": "defaults.level_name",
                "value": "Mi Mundo 1",
                "category": "defaults",
                "description": "Nombre del mundo por defecto de un servidor nuevo",
                "updated_by": "migration",
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    """Revoca la migración."""
    for role in _ROLES:
        op.execute(
            f"DELETE FROM iam_role_permissions WHERE role = '{role}' "
            f"AND permission_code = '{_CODE}'"
        )
    op.execute(f"DELETE FROM iam_permissions WHERE code = '{_CODE}'")
    op.execute("DELETE FROM settings WHERE key = 'defaults.level_name'")
    op.drop_column("world_metadata", "view_distance")
    op.drop_column("world_metadata", "difficulty")
    op.drop_column("world_metadata", "gamemode")
    op.drop_column("world_metadata", "seed")
