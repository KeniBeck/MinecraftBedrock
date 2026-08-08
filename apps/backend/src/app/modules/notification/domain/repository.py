"""Puerto de persistencia del ``EventLog`` (append-only, TDD §15.8).

El ``EventLog`` es el registro inmutable de eventos ya difundidos por el
gateway; permite ``resume`` por ``seq`` sin tocar los eventos de negocio. El
``seq`` es global y monótono (una secuencia en Postgres); se asigna en el
momento de la publicación y queda persistido. No se permiten updates/borrados
(política append-only; la retención futura es tarea del operador).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class EventLogEntry:
    """Entrada persistida del ``EventLog`` (append-only)."""

    seq: int
    event_type: str
    scope: str
    server_id: str | None
    user_id: str | None
    payload: dict[str, Any]
    created_at: datetime


class EventLogRepositoryPort(Protocol):
    """Contrato de persistencia del registro de eventos del gateway."""

    async def next_seq(self) -> int:
        """Devuelve y consume el siguiente valor de secuencia global."""

    async def append(self, entry: EventLogEntry) -> None:
        """Persiste una entrada ya numerada (append-only)."""

    async def get_events_since(
        self,
        last_seq: int,
        *,
        scope: str | None = None,
        server_id: str | None = None,
        user_id: str | None = None,
        limit: int = 1000,
    ) -> list[EventLogEntry]:
        """Eventos con ``seq > last_seq`` del canal indicado, en orden."""

    async def latest_seq(self) -> int:
        """Último ``seq`` persistido (0 si el log está vacío)."""
