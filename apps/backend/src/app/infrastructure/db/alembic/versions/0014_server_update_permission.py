"""Migración por módulo: permiso ``server.update`` (extensión paso 19).

El catálogo de la migración 0012 no incluye ``server.update``; se añade el
código y se concede a los roles que tienen escritura sobre servidores
(operator/admin/super_admin) para BBDD ya migradas.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_server_update_permission"
down_revision: str | None = "0013_settings_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CODE = "server.update"
_CATEGORY = "server"
_ROLES = ("operator", "admin", "super_admin")


def upgrade() -> None:
    """Inserta el permiso ``server.update`` y lo concede a los roles de escritura."""
    op.execute(
        f"INSERT INTO iam_permissions (code, category, description) "
        f"VALUES ('{_CODE}', '{_CATEGORY}', 'Actualizar recursos/atributos de un servidor') "
        f"ON CONFLICT (code) DO NOTHING"
    )
    for role in _ROLES:
        op.execute(
            f"INSERT INTO iam_role_permissions (role, permission_code) "
            f"VALUES ('{role}', '{_CODE}') ON CONFLICT DO NOTHING"
        )


def downgrade() -> None:
    """Revoca la migración."""
    for role in _ROLES:
        op.execute(
            f"DELETE FROM iam_role_permissions WHERE role = '{role}' "
            f"AND permission_code = '{_CODE}'"
        )
    op.execute(f"DELETE FROM iam_permissions WHERE code = '{_CODE}'")
