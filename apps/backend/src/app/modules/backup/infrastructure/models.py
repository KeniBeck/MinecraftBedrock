"""Modelos SQLAlchemy del módulo Backup (prefijo ``backup_*``).

``BackupRow`` registra la metadata del artefacto (el contenido vive en el
``BackupStorePort``; ``storage_ref`` es opaco). Sin FKs a otros módulos
(bounded contexts, mismo criterio que World/Player).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class BackupRow(Base):
    """Registro de un artefacto de backup de un mundo."""

    __tablename__ = "backup_backups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    world_name: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_ref: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    entries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    duration_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    orphaned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
