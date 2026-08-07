"""Eventos de dominio ``CONFIG.*`` (Blueprint §9.3).

Configuration publica ``CONFIG.CHANGED`` cuando cambia la *config deseada*
(properties/versión); Server la consume y la aplica (Blueprint §5.4). El tema
de suscripción se deriva del tipo (§10.3): ``config.changed``.
"""

from __future__ import annotations

from app.kernel.events.event import DomainEvent

CONFIG_CHANGED = "CONFIG.CHANGED"
CONFIG_CHANGED_TOPIC = "config.changed"


def config_changed(
    server_id: str,
    config_rev: int,
    *,
    actor_id: str | None = None,
) -> DomainEvent:
    """Config deseada modificada (payload: ``server_id`` + ``config_rev``)."""
    return DomainEvent(
        type=CONFIG_CHANGED,
        event_id="",
        server_id=server_id,
        actor_id=actor_id,
        payload={"server_id": server_id, "config_rev": config_rev},
    )
