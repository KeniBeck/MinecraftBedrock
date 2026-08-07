"""Eventos de dominio ``SERVER.*`` (Blueprint §9.1, TDD §7.2).

Los eventos se construyen aquí con tipos canónicos y se publican únicamente
vía ``EventBusPort`` (ADR-001: bus en proceso, sin outbox todavía).
"""

from __future__ import annotations

from typing import Any

from app.kernel.events.event import DomainEvent

SERVER_CREATED = "SERVER.CREATED"
SERVER_CONFIG_CHANGED = "SERVER.CONFIG_CHANGED"
SERVER_STARTING = "SERVER.STARTING"
SERVER_STARTED = "SERVER.STARTED"
SERVER_STOPPING = "SERVER.STOPPING"
SERVER_STOPPED = "SERVER.STOPPED"
SERVER_CRASHED = "SERVER.CRASHED"
SERVER_REMOVED = "SERVER.REMOVED"
SERVER_VERSION_CHANGED = "SERVER.VERSION_CHANGED"

SERVER_TOPIC_WILDCARD = "server.*"

CONFIG_CHANGED_TOPIC = "config.changed"
WORLD_ACTIVATED_TOPIC = "world.activated"


def topic_for(event_type: str) -> str:
    """Tema de suscripción derivado del tipo (Blueprint §10.3)."""
    return event_type.lower()


def server_event(
    event_type: str,
    server_id: str,
    *,
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> DomainEvent:
    """Construye un evento de dominio ``SERVER.*`` normalizado."""
    return DomainEvent(
        type=event_type,
        event_id="",
        server_id=server_id,
        actor_id=actor_id,
        payload=payload or {},
    )
