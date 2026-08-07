"""Eventos de dominio ``WORLD.*`` (Blueprint §3.3, §9.2).

World publica la vida del mundo (creado/importado/exportado/duplicado/
eliminado/activado). ``WORLD.ACTIVATED`` lo consume el módulo Server
(``WorldActivatedHandler``) para reaplicar la config (level-name). El payload
de ``WORLD.ACTIVATED`` **no** lleva ``config_rev``: World no conoce las
revisiones de Configuration (decisión §22), el handler lo trata como
"reaplicar sin cambiar la revisión".
"""

from __future__ import annotations

from app.kernel.events.event import DomainEvent

WORLD_CREATED = "WORLD.CREATED"
WORLD_IMPORTED = "WORLD.IMPORTED"
WORLD_EXPORTED = "WORLD.EXPORTED"
WORLD_DUPLICATED = "WORLD.DUPLICATED"
WORLD_DELETED = "WORLD.DELETED"
WORLD_ACTIVATED = "WORLD.ACTIVATED"

WORLD_CREATED_TOPIC = "world.created"
WORLD_IMPORTED_TOPIC = "world.imported"
WORLD_EXPORTED_TOPIC = "world.exported"
WORLD_DUPLICATED_TOPIC = "world.duplicated"
WORLD_DELETED_TOPIC = "world.deleted"
WORLD_ACTIVATED_TOPIC = "world.activated"


def world_event(
    event_type: str,
    server_id: str,
    name: str,
    *,
    actor_id: str | None = None,
    extra: dict[str, object] | None = None,
) -> DomainEvent:
    """Construye un evento ``WORLD.*`` normalizado (payload canónico)."""
    payload: dict[str, object] = {"server_id": server_id, "name": name}
    if extra:
        payload.update(extra)
    return DomainEvent(
        type=event_type,
        event_id="",
        server_id=server_id,
        actor_id=actor_id,
        payload=payload,
    )
