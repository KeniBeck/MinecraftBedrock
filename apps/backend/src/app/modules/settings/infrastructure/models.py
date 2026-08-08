"""Modelos SQLAlchemy del módulo Settings (Fase H paso 19, tabla ``settings``).

Clave única (``key``) + valor JSONB + categoría + metadatos de auditoría. Sin
FK a ``iam_users`` para mantener bounded contexts desacoplados (el ``updated_by``
es un id de usuario; la validación de identidad la hace IAM).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class SettingRow(Base):
    """Ajuste persistido del panel (DB es la fuente principal tras el paso 19)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
