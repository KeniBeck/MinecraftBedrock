"""Modelo SQLAlchemy del agregado ``Server`` (Fase A paso 2, tabla ``server_*``).

Mapeo físico del agregado según TDD §15.2 y el dominio ``Server``: identidad,
``RuntimeSpec`` (jsonb) con columnas desnormalizadas imagen/tag/versión para
consulta, estado normalizado y timestamps. El prefijo ``server_`` respeta los
bounded contexts (Blueprint §10.5).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ServerRow(Base):
    """Fila de un servidor del panel."""

    __tablename__ = "server_servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    image: Mapped[str] = mapped_column(Text, nullable=False)
    tag: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    spec: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    runtime_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    desired_config_rev: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applied_config_rev: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
