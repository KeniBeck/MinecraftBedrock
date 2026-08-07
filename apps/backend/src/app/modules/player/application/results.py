"""Vistas de salida de los use cases del módulo Player (proyecciones, §4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
