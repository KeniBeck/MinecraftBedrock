"""Modelos SQLAlchemy del módulo Player (prefijo ``player_*``).

``PlayerRow`` (caché de identidad + playtime), ``PlaySessionRow`` (presencia
por servidor) y los agregados de ban ``GlobalBanRow``/``ServerBanRow``
(ADR-011: matching con fallback xuid→gamertag en offline). Sin FKs a otros
módulos (bounded contexts, mismo criterio que IAM/Configuration).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
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


class GlobalBanRow(Base):
    """Ban de panel-wide: no pertenece a un servidor (agregado ``GlobalBan``)."""

    __tablename__ = "player_global_bans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    xuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gamertag: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    banned_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ServerBanRow(Base):
    """Ban por servidor (agregado ``ServerBan``, atado a ``server_id``)."""

    __tablename__ = "player_server_bans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    server_id: Mapped[str] = mapped_column(String(36), nullable=False)
    xuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gamertag: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    banned_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# Unicidad sobre el gamertag normalizado (lower-case) para evitar duplicados
# y lookups por xuid (cuando no sea null), según la spec de player_global_bans.
Index("uq_player_global_bans_gamertag", func.lower(GlobalBanRow.gamertag), unique=True)
Index("ix_player_global_bans_xuid", GlobalBanRow.xuid)
Index(
    "uq_player_server_bans_server_gamertag",
    ServerBanRow.server_id,
    func.lower(ServerBanRow.gamertag),
    unique=True,
)
Index("ix_player_server_bans_server_xuid", ServerBanRow.server_id, ServerBanRow.xuid)
