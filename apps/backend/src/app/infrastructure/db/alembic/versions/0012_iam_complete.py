"""Migración por módulo: IAM completo (Fase H paso 18).

Matriz de permisos por acción (``iam_permissions`` + ``iam_role_permissions``),
API keys (``iam_api_keys``), campos 2FA en ``iam_users`` y columnas de cadena
de hash en ``iam_audit_logs``. La siembra del catálogo base y de la matriz por
rol se hace aquí (idempotente por diseño: tablas nuevas).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012_iam_complete"
down_revision: str | None = "0011_noti_event_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Catálogo de permisos: (code, category). Fuente única = ``domain/permissions.py``.
_CATALOG: tuple[tuple[str, str], ...] = (
    ("server.list", "server"),
    ("server.view", "server"),
    ("server.status", "server"),
    ("server.status.read", "server"),
    ("server.create", "server"),
    ("server.start", "server"),
    ("server.stop", "server"),
    ("server.restart", "server"),
    ("server.delete", "server"),
    ("server.update", "server"),
    ("server.config.apply", "server"),
    ("server.config.update", "server"),
    ("server.version.change", "server"),
    ("server.version.update", "server"),
    ("server.console.read", "server"),
    ("server.console.write", "server"),
    ("world.list", "world"),
    ("world.view", "world"),
    ("world.create", "world"),
    ("world.import", "world"),
    ("world.export", "world"),
    ("world.duplicate", "world"),
    ("world.activate", "world"),
    ("world.delete", "world"),
    ("world.sync", "world"),
    ("backup.list", "backup"),
    ("backup.view", "backup"),
    ("backup.create", "backup"),
    ("backup.restore", "backup"),
    ("backup.delete", "backup"),
    ("backup.validate", "backup"),
    ("backup.prune", "backup"),
    ("backup.download", "backup"),
    ("player.list", "player"),
    ("player.view", "player"),
    ("player.manage", "player"),
    ("player.sessions", "player"),
    ("player.online", "player"),
    ("player.ban.global", "player"),
    ("permission.read", "permission"),
    ("permission.write", "permission"),
    ("console.view", "console"),
    ("console.command", "console"),
    ("template.list", "template"),
    ("template.view", "template"),
    ("template.capture", "template"),
    ("template.apply", "template"),
    ("template.delete", "template"),
    ("task.list", "scheduler"),
    ("task.view", "scheduler"),
    ("task.create", "scheduler"),
    ("task.update", "scheduler"),
    ("task.delete", "scheduler"),
    ("task.run", "scheduler"),
    ("scheduler.task.create", "scheduler"),
    ("iam.user.create", "iam"),
    ("iam.user.update", "iam"),
    ("iam.user.delete", "iam"),
    ("iam.user.role.assign", "iam"),
    ("iam.user.membership.assign", "iam"),
    ("iam.role.assign", "iam"),
    ("iam.audit.view", "iam"),
    ("iam.apikey.create", "iam"),
    ("iam.apikey.manage", "iam"),
    ("settings.view", "settings"),
    ("settings.update", "settings"),
)

_READ_ACTIONS: frozenset[str] = frozenset(
    {
        "server.list",
        "server.view",
        "server.status",
        "server.status.read",
        "server.console.read",
        "world.list",
        "world.view",
        "world.export",
        "backup.list",
        "backup.view",
        "backup.download",
        "player.list",
        "player.view",
        "player.sessions",
        "player.online",
        "permission.read",
        "console.view",
        "task.list",
        "task.view",
        "template.list",
        "template.view",
        "settings.view",
    }
)

_PANEL_ACTIONS: frozenset[str] = frozenset(
    {
        "server.create",
        "player.ban.global",
        "iam.user.create",
        "iam.user.update",
        "iam.user.delete",
        "iam.user.role.assign",
        "iam.user.membership.assign",
        "iam.role.assign",
        "iam.audit.view",
        "iam.apikey.create",
        "iam.apikey.manage",
        "settings.update",
    }
)

_ALL = frozenset(code for code, _ in _CATALOG)
_WRITE = _ALL - _READ_ACTIONS - _PANEL_ACTIONS


def _codes_for(role: str) -> tuple[str, ...]:
    if role in ("super_admin", "admin"):
        return tuple(sorted(_ALL))
    if role == "operator":
        return tuple(sorted(_READ_ACTIONS | _WRITE))
    return tuple(sorted(_READ_ACTIONS))


def upgrade() -> None:
    """Crea la matriz de permisos, API keys y columnas de 2FA/hash-chain."""
    op.create_table(
        "iam_permissions",
        sa.Column("code", sa.String(length=64), primary_key=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_table(
        "iam_role_permissions",
        sa.Column("role", sa.String(length=16), primary_key=True),
        sa.Column("permission_code", sa.String(length=64), primary_key=True),
    )
    op.create_table(
        "iam_api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "scopes",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_iam_api_keys_user_id", "iam_api_keys", ["user_id"], unique=False)
    op.create_index("ix_iam_api_keys_key_hash", "iam_api_keys", ["key_hash"], unique=True)

    op.add_column("iam_users", sa.Column("totp_secret", sa.Text(), nullable=True))
    op.add_column(
        "iam_users",
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("iam_users", sa.Column("backup_codes", sa.Text(), nullable=True))

    op.add_column("iam_audit_logs", sa.Column("prev_hash", sa.Text(), nullable=True))
    op.add_column("iam_audit_logs", sa.Column("hash", sa.Text(), nullable=True))

    _seed_catalog()


def _seed_catalog() -> None:
    """Sembra el catálogo y la matriz por rol (tablas nuevas: idempotente)."""
    op.bulk_insert(
        sa.table(
            "iam_permissions",
            sa.column("code", sa.String),
            sa.column("category", sa.String),
            sa.column("description", sa.Text),
        ),
        [
            {"code": code, "category": category, "description": f"{code} ({category})"}
            for code, category in _CATALOG
        ],
    )
    rows = [
        {"role": role, "permission_code": code}
        for role in ("super_admin", "admin", "operator", "viewer")
        for code in _codes_for(role)
    ]
    op.bulk_insert(
        sa.table(
            "iam_role_permissions",
            sa.column("role", sa.String),
            sa.column("permission_code", sa.String),
        ),
        rows,
    )


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_column("iam_audit_logs", "hash")
    op.drop_column("iam_audit_logs", "prev_hash")
    op.drop_column("iam_users", "backup_codes")
    op.drop_column("iam_users", "totp_enabled")
    op.drop_column("iam_users", "totp_secret")
    op.drop_index("ix_iam_api_keys_key_hash", table_name="iam_api_keys")
    op.drop_index("ix_iam_api_keys_user_id", table_name="iam_api_keys")
    op.drop_table("iam_api_keys")
    op.drop_table("iam_role_permissions")
    op.drop_table("iam_permissions")
