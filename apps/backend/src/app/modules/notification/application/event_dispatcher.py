"""Consumidor del bus → canal del gateway (Blueprint §3.12).

``EventDispatcher`` se suscribe al ``EventBusPort`` y, por cada ``DomainEvent``
de alcance frontend, determina los canales destino, asigna el ``seq`` global
persistiendo en el ``EventLog`` y difunde el envelope a las conexiones
suscritas. Nunca propaga excepciones al bus: los errores se loguean.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.kernel.events.bus import EventHandler
from app.kernel.events.event import DomainEvent, EventEnvelope
from app.modules.notification.application.connection_manager import ConnectionManager
from app.modules.notification.domain.events import (
    SCOPE_GLOBAL,
    SCOPE_SERVER,
    SCOPE_USER,
    channel_name,
    event_scope,
)
from app.modules.notification.domain.repository import EventLogEntry, EventLogRepositoryPort

logger = logging.getLogger(__name__)


def serialize_envelope(envelope: EventEnvelope) -> dict[str, object]:
    """Serializa un envelope al formato del wire (§13.2)."""
    return {
        "event": envelope.event,
        "server_id": envelope.server_id,
        "scope": envelope.scope,
        "payload": envelope.payload,
        "ts": envelope.ts.isoformat(),
        "seq": envelope.seq,
    }


def resolve_channels(event: DomainEvent) -> set[str]:
    """Canales destino de un evento de dominio (Blueprint §3.12).

    Si el evento lleva ``server_id`` siempre va al canal ``server:{id}``; si
    no, se usa ``event_scope`` sobre el tipo: eventos de IAM/AUTH al canal
    ``user:{actor_id}``; el resto a ``global``.
    """
    if event.server_id:
        return {channel_name(SCOPE_SERVER, event.server_id)}
    scope = event_scope(event.type)
    if scope == SCOPE_USER and event.actor_id:
        return {channel_name(SCOPE_USER, event.actor_id)}
    return {channel_name(SCOPE_GLOBAL, None)}


class EventDispatcher:
    """Escucha el bus y difunde a los canales del gateway."""

    def __init__(
        self,
        *,
        connections: ConnectionManager,
        event_log: EventLogRepositoryPort,
    ) -> None:
        self._connections = connections
        self._event_log = event_log

    @property
    def connections(self) -> ConnectionManager:
        return self._connections

    def handler(self) -> EventHandler:
        return self._dispatch

    async def _dispatch(self, event: DomainEvent) -> None:
        try:
            await self._forward(event)
        except Exception:  # noqa: BLE001 - el gateway no debe romper el bus
            logger.exception("Fallo difundiendo evento %s", event.type)

    async def _forward(self, event: DomainEvent) -> None:
        now = datetime.now(UTC)
        scope = SCOPE_SERVER if event.server_id else event_scope(event.type)
        seq = await self._event_log.next_seq()
        await self._event_log.append(
            EventLogEntry(
                seq=seq,
                event_type=event.type,
                scope=scope,
                server_id=event.server_id,
                user_id=event.actor_id if scope == SCOPE_USER else None,
                payload=dict(event.payload),
                created_at=now,
            )
        )
        envelope = EventEnvelope(
            event=event.type,
            scope=scope,
            payload=dict(event.payload),
            ts=now,
            seq=seq,
            server_id=event.server_id,
        )
        channels = resolve_channels(event)
        self._connections.broadcast_to_channels(channels, serialize_envelope(envelope))
