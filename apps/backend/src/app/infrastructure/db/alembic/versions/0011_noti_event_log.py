"""Migración por módulo: tablas del dominio Notification (prefijo ``noti_*``).

Fase H paso 17 — ``noti_event_log`` es el ``EventLog`` append-only del gateway
(§15.8): un registro por evento difundido, con ``seq`` global monótono desde la
secuencia ``noti_event_log_seq``. Sin FKs a otros módulos (bounded contexts,
mismo criterio que Server/Console/etc).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_noti_event_log"
down_revision: str | None = "0010_template_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "noti_event_log"
_SEQ = "noti_event_log_seq"


def upgrade() -> None:
    """Crea ``noti_event_log`` y su secuencia de ``seq``."""
    op.execute(f"CREATE SEQUENCE IF NOT EXISTS {_SEQ}")
    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("seq", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("server_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_noti_event_log_scope_seq", _TABLE, ["scope", "server_id", "seq"])


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_index("ix_noti_event_log_scope_seq", table_name=_TABLE)
    op.drop_table(_TABLE)
    op.execute(f"DROP SEQUENCE IF EXISTS {_SEQ}")
