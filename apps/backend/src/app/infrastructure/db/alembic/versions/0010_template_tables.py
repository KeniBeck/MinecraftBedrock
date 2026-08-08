"""Migración por módulo: tabla del dominio Template (prefijo ``template_*``).

Fase G paso 16 — ``TemplateRow`` (metadata de plantillas ``.mctemplate``).
El artefacto binario vive en el filesystem (``TemplateArchiveStore``), no en
BBDD. Sin FKs a otros módulos (bounded contexts, mismo criterio que Backup/
Scheduler/Player). El nombre es único (``name``) para no duplicar plantillas.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_template_tables"
down_revision: str | None = "0009_scheduler_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Crea ``template_templates``."""
    op.create_table(
        "template_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("origin_server_id", sa.String(length=36), nullable=True),
        sa.Column("origin_world", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_table("template_templates")
