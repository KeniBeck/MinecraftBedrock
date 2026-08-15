"""Migración por módulo: avatar de usuario (Fase 8).

Añade la columna ``avatar`` (Text, nullable) a ``iam_users``. Guarda el avatar
como data URL base64 (``data:image/<png|jpeg|webp>;base64,...``) generada en el
endpoint ``PUT /users/me/avatar`` (self-service, autenticado).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_iam_user_avatar"
down_revision: str | None = "0016_iam_user_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Añade la columna avatar (data URL base64)."""
    op.add_column("iam_users", sa.Column("avatar", sa.Text(), nullable=True))


def downgrade() -> None:
    """Revoca la migración."""
    op.drop_column("iam_users", "avatar")
