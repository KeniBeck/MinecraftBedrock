"""Modelos SQLAlchemy del módulo Player (prefijo ``player_*``).

``PlayerRow`` (caché de identidad + playtime) y ``PlaySessionRow`` (presencia
por servidor). Sin FKs a otros módulos (bounded contexts, mismo criterio que
IAM/Configuration).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class PlayerRow(Base):
    """Jugador conocido por el panel (identidad = XUID, nunca el gamertag)."""

    __tablename__ = "player_players"

    xuid: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    playtime_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlaySessionRow(Base):
    """Sesión de juego de un jugador en un servidor (abierta/cerrada)."""

    __tablename__ = "player_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    xuid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    playtime_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
