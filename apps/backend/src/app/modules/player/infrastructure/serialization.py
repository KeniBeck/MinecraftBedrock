"""Serialización del dominio Player ↔ filas (test sin BBDD)."""

from __future__ import annotations

from typing import Any

from app.modules.player.domain.player import Player
from app.modules.player.domain.session import PlaySession, SessionEndReason
from app.modules.player.infrastructure.models import PlayerRow, PlaySessionRow


def player_to_row(player: Player) -> dict[str, Any]:
    """Proyección de ``Player`` a los campos de ``PlayerRow``."""
    return {
        "xuid": player.xuid,
        "name": player.name,
        "first_seen_at": player.first_seen_at,
        "last_seen_at": player.last_seen_at,
        "playtime_seconds": player.playtime_seconds,
        "created_at": player.created_at,
        "updated_at": player.updated_at,
    }


def player_from_row(row: PlayerRow) -> Player:
    """Reconstruye ``Player`` desde una fila."""
    return Player(
        xuid=row.xuid,
        name=row.name,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        playtime_seconds=row.playtime_seconds,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def session_to_row(session: PlaySession) -> dict[str, Any]:
    """Proyección de ``PlaySession`` a los campos de ``PlaySessionRow``."""
    return {
        "id": session.id,
        "server_id": session.server_id,
        "xuid": session.xuid,
        "joined_at": session.joined_at,
        "left_at": session.left_at,
        "reason": session.reason.value if session.reason is not None else None,
        "playtime_seconds": session.playtime_seconds,
    }


def session_from_row(row: PlaySessionRow) -> PlaySession:
    """Reconstruye ``PlaySession`` desde una fila."""
    return PlaySession(
        id=row.id,
        server_id=row.server_id,
        xuid=row.xuid,
        joined_at=row.joined_at,
        left_at=row.left_at,
        reason=SessionEndReason(row.reason) if row.reason is not None else None,
        playtime_seconds=row.playtime_seconds,
    )
