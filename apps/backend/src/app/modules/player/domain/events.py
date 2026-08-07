"""Eventos de dominio ``PLAYER.*`` (Blueprint §9.2).

``PLAYER.JOINED``/``PLAYER.LEFT`` los publican los **parsers declarativos** de
``infrastructure/parsers`` (detección de líneas de join/leave del log, §7.3),
**no** el módulo Player: Player solo los consume. ``PLAYER.BANNED`` lo publica
Player cuando ejecuta un ban vía la facade Console. ``PLAYER.OPERATOR_CHANGED``
lo publica Permission (Fase F); Player solo lo consume (consistencia).
"""

from __future__ import annotations

from app.kernel.events.event import DomainEvent

PLAYER_JOINED = "PLAYER.JOINED"
PLAYER_LEFT = "PLAYER.LEFT"
PLAYER_BANNED = "PLAYER.BANNED"
PLAYER_OPERATOR_CHANGED = "PLAYER.OPERATOR_CHANGED"

PLAYER_JOINED_TOPIC = "player.joined"
PLAYER_LEFT_TOPIC = "player.left"
PLAYER_BANNED_TOPIC = "player.banned"
PLAYER_OPERATOR_CHANGED_TOPIC = "player.operator_changed"


def player_joined(server_id: str, name: str, xuid: str) -> DomainEvent:
    """Jugador conectado detectado por un parser declarativo (§7.3)."""
    return DomainEvent(
        type=PLAYER_JOINED,
        event_id="",
        server_id=server_id,
        payload={"server_id": server_id, "name": name, "xuid": xuid},
    )


def player_left(server_id: str, name: str, xuid: str) -> DomainEvent:
    """Jugador desconectado (o timed out) detectado por un parser declarativo."""
    return DomainEvent(
        type=PLAYER_LEFT,
        event_id="",
        server_id=server_id,
        payload={"server_id": server_id, "name": name, "xuid": xuid},
    )


def player_banned(
    server_id: str,
    xuid: str,
    name: str,
    command: str,
    *,
    actor_id: str | None = None,
) -> DomainEvent:
    """Ban ejecutado por el panel vía la facade Console (Blueprint §9.2)."""
    return DomainEvent(
        type=PLAYER_BANNED,
        event_id="",
        server_id=server_id,
        actor_id=actor_id,
        payload={"server_id": server_id, "xuid": xuid, "name": name, "command": command},
    )


def player_operator_changed(
    server_id: str,
    xuid: str,
    operator: bool,
    *,
    actor_id: str | None = None,
) -> DomainEvent:
    """Estado de operador modificado por Permission (consumido por Player)."""
    return DomainEvent(
        type=PLAYER_OPERATOR_CHANGED,
        event_id="",
        server_id=server_id,
        actor_id=actor_id,
        payload={"server_id": server_id, "xuid": xuid, "operator": operator},
    )
