"""Eventos de dominio de Permission (Blueprint §3.6, §9.2).

``PLAYER.OPERATOR_CHANGED`` se publica al asignar/remover el nivel de
operador y lo consume Player. ``PERMISSION.ALLOWLIST_TOGGLED`` se publica al
cambiar el toggle ``ALLOW_LIST`` y lo consume Server para inyectar la env var
``ALLOW_LIST`` en el spec y recrear el contenedor (mismo mecanismo que
``WORLD.ACTIVATED``/``LEVEL_NAME``).
"""

from __future__ import annotations

from app.kernel.events.event import DomainEvent

PLAYER_OPERATOR_CHANGED = "PLAYER.OPERATOR_CHANGED"
PLAYER_OPERATOR_CHANGED_TOPIC = "player.operator_changed"

ALLOWLIST_TOGGLED = "PERMISSION.ALLOWLIST_TOGGLED"
ALLOWLIST_TOGGLED_TOPIC = "permission.allowlist_toggled"


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


def allowlist_toggled(
    server_id: str,
    enabled: bool,
    *,
    actor_id: str | None = None,
) -> DomainEvent:
    """Toggle ``ALLOW_LIST`` modificado (consumido por Server para recrear)."""
    return DomainEvent(
        type=ALLOWLIST_TOGGLED,
        event_id="",
        server_id=server_id,
        actor_id=actor_id,
        payload={"server_id": server_id, "enabled": enabled},
    )
