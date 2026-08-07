"""Eventos de dominio (TDD §7, Blueprint §9).

Todo evento lleva ``event_id``, ``type``, ``occurred_at``, ``server_id?``,
``actor_id?``, ``payload`` y ``schema_version`` (Blueprint §9.8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Evento de dominio publicado a través del ``EventBusPort``."""

    type: str
    occurred_at: datetime = field(default_factory=_utcnow)
    event_id: str = ""
    server_id: str | None = None
    actor_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Envolvente de salida WebSocket (Blueprint §13.2)."""

    event: str
    scope: str
    payload: dict[str, Any]
    ts: datetime = field(default_factory=_utcnow)
    seq: int = 0
    server_id: str | None = None
