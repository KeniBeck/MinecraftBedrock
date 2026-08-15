"""Migración por módulo: gestión de usuarios IAM (Fase 8).

Añade la columna ``email`` (nullable) a ``iam_users`` y extiende el catálogo de
permisos con ``iam.view`` (lectura: listado/detalle/roles/auditoría, viewer+) e
``iam.manage`` (escritura: editar/suspender/eliminar usuarios, admin+). La
inserción de permisos es idempotente por diseño: ``ON CONFLICT DO NOTHING``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_iam_user_management"
down_revision: str | None = "0015_world_world_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PERMISSION_CODES: tuple[tuple[str, str], ...] = (
    ("iam.view", "iam"),
    ("iam.manage", "iam"),
)

# Rol → códigos nuevos: iam.view llega hasta viewer (READ_ACTION); iam.manage
# solo admin/super_admin (PANEL_ACTION).
_ROLE_GRANTS: tuple[tuple[str, str], ...] = (
    ("super_admin", "iam.view"),
    ("super_admin", "iam.manage"),
    ("admin", "iam.view"),
    ("admin", "iam.manage"),
    ("operator", "iam.view"),
    ("viewer", "iam.view"),
)


def upgrade() -> None:
    """Añade email y extiende el catálogo de permisos."""
    op.add_column("iam_users", sa.Column("email", sa.String(length=255), nullable=True))

    permissions = sa.table(
        "iam_permissions",
        sa.column("code", sa.String),
        sa.column("category", sa.String),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        permissions,
        [
            {"code": code, "category": category, "description": f"{code} ({category})"}
            for code, category in _PERMISSION_CODES
        ],
    )
    role_permissions = sa.table(
        "iam_role_permissions",
        sa.column("role", sa.String),
        sa.column("permission_code", sa.String),
    )
    op.bulk_insert(
        role_permissions,
        [{"role": role, "permission_code": code} for role, code in _ROLE_GRANTS],
    )


def downgrade() -> None:
    """Revoca la migración."""
    role_permissions = sa.table(
        "iam_role_permissions",
        sa.column("role", sa.String),
        sa.column("permission_code", sa.String),
    )
    for role, code in _ROLE_GRANTS:
        op.execute(
            role_permissions.delete().where(
                sa.and_(
                    role_permissions.c.role == role,
                    role_permissions.c.permission_code == code,
                )
            )
        )
    permissions = sa.table("iam_permissions", sa.column("code", sa.String))
    for code, _ in _PERMISSION_CODES:
        op.execute(permissions.delete().where(permissions.c.code == code))
    op.drop_column("iam_users", "email")
