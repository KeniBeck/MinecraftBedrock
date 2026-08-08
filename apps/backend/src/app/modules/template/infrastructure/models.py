"""Modelos SQLAlchemy del módulo Template (prefijo ``template_*``).

``TemplateRow`` registra la metadata de una plantilla ``.mctemplate``. Sin FKs
a otros módulos (bounded contexts, mismo criterio que Backup/Scheduler/Player).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class TemplateRow(Base):
    """Metadata de una plantilla capturada del estado de un servidor."""

    __tablename__ = "template_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    origin_server_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    origin_world: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
