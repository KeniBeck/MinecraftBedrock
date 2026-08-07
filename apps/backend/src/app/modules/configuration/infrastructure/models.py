"""Modelos SQLAlchemy del módulo Configuration (ADR-004, prefijo ``config_``).

``ConfigProfileRow`` (estado deseado) y ``ConfigHistoryRow`` (historial
append-only por servidor, PK compuesta server_id+config_rev).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ConfigProfileRow(Base):
    """Config deseada de un servidor (properties + revisión + aplicado)."""

    __tablename__ = "config_profiles"

    server_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    config_rev: Mapped[int] = mapped_column(Integer, nullable=False)
    applied: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConfigHistoryRow(Base):
    """Historial append-only de config por servidor (auditoría, ADR-004)."""

    __tablename__ = "config_history"

    server_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    config_rev: Mapped[int] = mapped_column(Integer, primary_key=True)
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False
    )
    version: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
