"""Repositorio ``EventLog`` en memoria (para tests y entornos sin BBDD).

Implementa ``EventLogRepositoryPort`` con ``seq`` global monótono relojado por
contador. La secuencia ``next_seq`` es el contador incrementado; ``append``
almacena la entrada; ``get_events_since`` filtra por canal y ordena por
``seq``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.notification.domain.repository import EventLogEntry


class InMemoryEventLogRepository:
    """``EventLog`` append-only en memoria con ``seq`` incremental."""

    def __init__(self) -> None:
        self._entries: list[EventLogEntry] = []
        self._counter = 0

    def clear(self) -> None:
        """Vacía el log y reinicia el contador (para determinismo en tests)."""
        self._entries = []
        self._counter = 0

    def seed(self, event_type: str, scope: str, server_id: str | None = None) -> int:
        """Registra una entrada numerada manualmente (para tests de resume)."""
        self._counter += 1
        entry = EventLogEntry(
            seq=self._counter,
            event_type=event_type,
            scope=scope,
            server_id=server_id,
            user_id=None,
            payload={},
            created_at=datetime.now(UTC),
        )
        self._entries.append(entry)
        return self._counter

    async def next_seq(self) -> int:
        self._counter += 1
        return self._counter

    async def append(self, entry: EventLogEntry) -> None:
        self._entries.append(entry)

    async def get_events_since(
        self,
        last_seq: int,
        *,
        scope: str | None = None,
        server_id: str | None = None,
        user_id: str | None = None,
        limit: int = 1000,
    ) -> list[EventLogEntry]:
        result = [
            entry
            for entry in self._entries
            if entry.seq > last_seq
            and (scope is None or entry.scope == scope)
            and (server_id is None or entry.server_id == server_id)
            and (user_id is None or entry.user_id == user_id)
        ]
        result = [entry for entry in result if entry.seq > last_seq]
        result.sort(key=lambda entry: entry.seq)
        return result[:limit]

    async def latest_seq(self) -> int:
        return max((entry.seq for entry in self._entries), default=0)
