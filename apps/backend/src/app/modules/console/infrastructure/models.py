"""Modelo SQLAlchemy del buffer de consola (Fase A paso 2, tabla ``console_*``).

Cada fila es una línea con su ``seq`` por servidor (PK compuesta) y un
``created_at`` de diagnóstico. La retención es **acotada y agresiva**: el
repositorio recorta las filas más antiguas al límite configurado, porque la
salida de consola es telemetría transitoria, no auditoría (criterio
documentado en el change-log, Fase A paso 2).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ConsoleLineRow(Base):
    """Fila de una línea de consola persistida."""

    __tablename__ = "console_lines"

    server_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    line: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
