"""Eventos de dominio ``PLAYER.*`` (Blueprint §9.2).

``PLAYER.JOINED``/``PLAYER.LEFT`` los publican los **parsers declarativos** de
``infrastructure/parsers`` (detección de líneas de join/leave del log, §7.3),
**no** el módulo Player: Player solo los consume. ``PLAYER.BANNED`` y
``PLAYER.UNBANNED`` los publica Player al crear/quitar un ban persistido
(global o por servidor); el propio Player aplica el kick al ``PLAYER.JOINED``
vía ``BanEnforcementHandler``. ``PLAYER.OPERATOR_CHANGED`` lo publica
Permission (Fase F); Player solo lo consume (consistencia).
"""

from __future__ import annotations

from app.kernel.events.event import DomainEvent

PLAYER_JOINED = "PLAYER.JOINED"
PLAYER_LEFT = "PLAYER.LEFT"
PLAYER_BANNED = "PLAYER.BANNED"
PLAYER_UNBANNED = "PLAYER.UNBANNED"
PLAYER_OPERATOR_CHANGED = "PLAYER.OPERATOR_CHANGED"

PLAYER_JOINED_TOPIC = "player.joined"
PLAYER_LEFT_TOPIC = "player.left"
PLAYER_BANNED_TOPIC = "player.banned"
PLAYER_UNBANNED_TOPIC = "player.unbanned"
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
    scope: str,
    xuid: str | None,
    gamertag: str,
    reason: str | None,
    *,
    server_id: str | None = None,
    actor_id: str | None = None,
) -> DomainEvent:
    """Ban persistido creado por el panel (payload: scope + identidad + motivo)."""
    return DomainEvent(
        type=PLAYER_BANNED,
        event_id="",
        server_id=server_id,
        actor_id=actor_id,
        payload={
            "scope": scope,
            "server_id": server_id,
            "xuid": xuid,
            "gamertag": gamertag,
            "reason": reason,
        },
    )


def player_unbanned(
    scope: str,
    xuid: str | None,
    gamertag: str,
    reason: str | None,
    *,
    server_id: str | None = None,
    ban_id: str = "",
    actor_id: str | None = None,
) -> DomainEvent:
    """Ban persistido removido por el panel (payload: scope + identidad + motivo)."""
    return DomainEvent(
        type=PLAYER_UNBANNED,
        event_id="",
        server_id=server_id,
        actor_id=actor_id,
        payload={
            "scope": scope,
            "server_id": server_id,
            "xuid": xuid,
            "gamertag": gamertag,
            "reason": reason,
            "ban_id": ban_id,
        },
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
