"""Migración por módulo: tabla del dominio Scheduler (prefijo ``scheduler_*``).

Fase G paso 15 — ``SchedulerTaskRow`` (tareas programadas recurrentes con cron).
Sin FKs a otros módulos (bounded contexts, mismo criterio que Backup/Player).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_scheduler_tables"
down_revision: str | None = "0008_player_ban_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea ``scheduler_tasks``."""
    op.create_table(
        "scheduler_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("server_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("cron", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result", sa.Text(), nullable=True),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("backoff_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_scheduler_tasks_server_id", "scheduler_tasks", ["server_id"])
    op.create_index("ix_scheduler_tasks_next_run_at", "scheduler_tasks", ["next_run_at"])


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_index("ix_scheduler_tasks_next_run_at", table_name="scheduler_tasks")
    op.drop_index("ix_scheduler_tasks_server_id", table_name="scheduler_tasks")
    op.drop_table("scheduler_tasks")
