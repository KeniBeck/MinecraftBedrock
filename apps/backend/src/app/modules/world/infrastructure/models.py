"""Modelos SQLAlchemy del módulo World (tabla ``world_metadata``).

Caché de metadata de mundos del servidor (la fuente de verdad del contenido es
el filesystem vía ``ServerStoragePort``). Sin FKs a otros módulos (bounded
contexts, mismo criterio que Player/IAM/Configuration).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class WorldRow(Base):
    """Metadata de un mundo de un servidor (identidad lógica server_id+name)."""

    __tablename__ = "world_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    level_name: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    activated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    seed: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gamemode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(32), nullable=True)
    view_distance: Mapped[int | None] = mapped_column(Integer, nullable=True)
