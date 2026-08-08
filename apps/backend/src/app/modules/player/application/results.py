"""Vistas de salida de los use cases del módulo Player (proyecciones, §4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.player.domain.bans import BanScope, GlobalBan, ServerBan
from app.modules.player.domain.player import Player
from app.modules.player.domain.session import PlaySession


@dataclass(frozen=True, slots=True)
class PlayerView:
    """Proyección de un jugador para consumidores externos (facade pública)."""

    xuid: str
    name: str
    first_seen_at: datetime
    last_seen_at: datetime
    playtime_seconds: int


@dataclass(frozen=True, slots=True)
class PlaySessionView:
    """Proyección de una sesión de juego."""

    id: str
    server_id: str
    xuid: str
    joined_at: datetime
    left_at: datetime | None
    reason: str | None
    playtime_seconds: int


@dataclass(frozen=True, slots=True)
class GlobalBanView:
    """Proyección de un ban global para consumidores externos."""

    id: str
    scope: str
    gamertag: str
    banned_by: str
    created_at: datetime
    xuid: str | None
    reason: str | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class ServerBanView:
    """Proyección de un ban por servidor para consumidores externos."""

    id: str
    scope: str
    server_id: str
    gamertag: str
    banned_by: str
    created_at: datetime
    xuid: str | None
    reason: str | None
    expires_at: datetime | None


def player_to_view(player: Player) -> PlayerView:
    """Proyecta un jugador del dominio a su vista de presentación."""
    return PlayerView(
        xuid=player.xuid,
        name=player.name,
        first_seen_at=player.first_seen_at,
        last_seen_at=player.last_seen_at,
        playtime_seconds=player.playtime_seconds,
    )


def session_to_view(session: PlaySession) -> PlaySessionView:
    """Proyecta una sesión del dominio a su vista de presentación."""
    return PlaySessionView(
        id=session.id,
        server_id=session.server_id,
        xuid=session.xuid,
        joined_at=session.joined_at,
        left_at=session.left_at,
        reason=session.reason.value if session.reason is not None else None,
        playtime_seconds=session.playtime_seconds,
    )


def global_ban_to_view(ban: GlobalBan) -> GlobalBanView:
    """Proyecta un ban global del dominio a su vista de presentación."""
    return GlobalBanView(
        id=ban.id,
        scope=BanScope.GLOBAL.value,
        gamertag=ban.gamertag,
        banned_by=ban.banned_by,
        created_at=ban.created_at,
        xuid=ban.xuid,
        reason=ban.reason,
        expires_at=ban.expires_at,
    )


def server_ban_to_view(ban: ServerBan) -> ServerBanView:
    """Proyecta un ban por servidor del dominio a su vista de presentación."""
    return ServerBanView(
        id=ban.id,
        scope=BanScope.SERVER.value,
        server_id=ban.server_id,
        gamertag=ban.gamertag,
        banned_by=ban.banned_by,
        created_at=ban.created_at,
        xuid=ban.xuid,
        reason=ban.reason,
        expires_at=ban.expires_at,
    )
