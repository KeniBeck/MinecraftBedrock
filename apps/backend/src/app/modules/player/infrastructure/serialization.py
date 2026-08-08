"""Serialización del dominio Player ↔ filas (test sin BBDD)."""

from __future__ import annotations

from typing import Any

from app.modules.player.domain.bans import GlobalBan, ServerBan
from app.modules.player.domain.player import Player
from app.modules.player.domain.session import PlaySession, SessionEndReason
from app.modules.player.infrastructure.models import (
    GlobalBanRow,
    PlayerRow,
    PlaySessionRow,
    ServerBanRow,
)


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


def global_ban_to_row(ban: GlobalBan) -> dict[str, Any]:
    """Proyección de ``GlobalBan`` a los campos de ``GlobalBanRow``."""
    return {
        "id": ban.id,
        "xuid": ban.xuid,
        "gamertag": ban.gamertag,
        "reason": ban.reason,
        "banned_by": ban.banned_by,
        "created_at": ban.created_at,
        "expires_at": ban.expires_at,
    }


def global_ban_from_row(row: GlobalBanRow) -> GlobalBan:
    """Reconstruye ``GlobalBan`` desde una fila."""
    return GlobalBan(
        id=row.id,
        xuid=row.xuid,
        gamertag=row.gamertag,
        reason=row.reason,
        banned_by=row.banned_by,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


def server_ban_to_row(ban: ServerBan) -> dict[str, Any]:
    """Proyección de ``ServerBan`` a los campos de ``ServerBanRow``."""
    return {
        "id": ban.id,
        "server_id": ban.server_id,
        "xuid": ban.xuid,
        "gamertag": ban.gamertag,
        "reason": ban.reason,
        "banned_by": ban.banned_by,
        "created_at": ban.created_at,
        "expires_at": ban.expires_at,
    }


def server_ban_from_row(row: ServerBanRow) -> ServerBan:
    """Reconstruye ``ServerBan`` desde una fila."""
    return ServerBan(
        id=row.id,
        server_id=row.server_id,
        xuid=row.xuid,
        gamertag=row.gamertag,
        reason=row.reason,
        banned_by=row.banned_by,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )
