"""Reenvío de eventos perdidos tras reconexión (``resume``, TDD §13.4).

Dado un ``last_seq`` y un conjunto de canales, consulta el ``EventLog`` por
canal y reconstruye en orden los envelopes con ``seq > last_seq``, hasta un
``limit`` configurable. Si el backlog pendiente supera el tope, lanza
``ResumeTooLargeError`` para que el cliente reconecte con un ``last_seq`` más
reciente.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.kernel.events.event import EventEnvelope
from app.modules.notification.application.event_dispatcher import serialize_envelope
from app.modules.notification.domain.events import (
    SCOPE_GLOBAL,
    SCOPE_SERVER,
    SCOPE_USER,
    parse_channel,
)
from app.modules.notification.domain.repository import (
    EventLogEntry,
    EventLogRepositoryPort,
)


@dataclass(frozen=True, slots=True)
class ResumeResult:
    """Envelopes a reenviar + si el backlog excedió el límite."""

    envelopes: list[dict[str, object]]
    exceeded: bool


class ResumeHandler:
    """Resuelve el reenvío de eventos posteriores a un ``last_seq``."""

    def __init__(self, event_log: EventLogRepositoryPort, limit: int = 1000) -> None:
        self._event_log = event_log
        self._limit = limit

    @property
    def limit(self) -> int:
        return self._limit

    async def resume(self, last_seq: int, channels: list[str]) -> ResumeResult:
        """Devuelve envelopes ordenados por ``seq`` para los canales dados."""
        merged: dict[int, EventEnvelope] = {}
        for name in channels:
            scope, key = parse_channel(name)
            entries = await self._fetch(scope, key, last_seq)
            for entry in entries:
                merged.setdefault(
                    entry.seq,
                    EventEnvelope(
                        event=entry.event_type,
                        scope=entry.scope,
                        payload=dict(entry.payload),
                        ts=entry.created_at,
                        seq=entry.seq,
                        server_id=entry.server_id,
                    ),
                )

        ordered = [envelope for _, envelope in sorted(merged.items())]
        exceeded = len(ordered) > self._limit
        return ResumeResult(
            envelopes=[serialize_envelope(envelope) for envelope in ordered[: self._limit]],
            exceeded=exceeded,
        )

    async def _fetch(self, scope: str, key: str | None, last_seq: int) -> list[EventLogEntry]:
        if scope == SCOPE_SERVER:
            return await self._event_log.get_events_since(
                last_seq, scope=scope, server_id=key or ""
            )
        if scope == SCOPE_USER:
            return await self._event_log.get_events_since(last_seq, scope=scope, user_id=key or "")
        if scope == SCOPE_GLOBAL:
            return await self._event_log.get_events_since(last_seq, scope=scope)
        return []
