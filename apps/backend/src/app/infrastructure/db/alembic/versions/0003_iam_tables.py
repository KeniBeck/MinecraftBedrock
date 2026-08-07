"""migración por módulo: tablas del dominio IAM (prefijo ``iam_*``).

Fase C paso 8 — mínimo viable: usuarios, roles globales, membresías por
servidor, sesiones de refresh y audit log básico (sin hash-chain).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_iam_tables"
down_revision: str | None = "0002_console_lines"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea las tablas ``iam_*`` (technical-design §15.1)."""
    op.create_table(
        "iam_users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_iam_users_username", "iam_users", ["username"], unique=True)

    op.create_table(
        "iam_user_roles",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("role", sa.String(length=16), primary_key=True),
    )

    op.create_table(
        "iam_server_memberships",
        sa.Column("server_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("role", sa.String(length=16), nullable=False),
    )

    op.create_table(
        "iam_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("ua", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_iam_sessions_user_id", "iam_sessions", ["user_id"], unique=False)
    op.create_index("ix_iam_sessions_token_hash", "iam_sessions", ["token_hash"], unique=True)

    op.create_table(
        "iam_audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=36), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column(
            "detail",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("ua", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_iam_audit_logs_actor_id", "iam_audit_logs", ["actor_id"], unique=False)
    op.create_index("ix_iam_audit_logs_action", "iam_audit_logs", ["action"], unique=False)


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_table("iam_audit_logs")
    op.drop_table("iam_sessions")
    op.drop_table("iam_server_memberships")
    op.drop_table("iam_user_roles")
    op.drop_table("iam_users")
