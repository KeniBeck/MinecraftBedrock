"""Contrato ``EventBusPort`` (Blueprint §4.6, TDD §7.1).

Bus en proceso con outbox (Fase 2) según ADR-001: la durabilidad se añade en
la implementación. Los dominios solo publican/consumen vía este puerto.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.kernel.events.event import DomainEvent

EventHandler = Callable[[DomainEvent], Awaitable[None] | None]


class EventBusPort(Protocol):
    """Publica y consume eventos de dominio (in-process, al-menos-una)."""

    async def publish(self, event: DomainEvent) -> None:
        """Persiste (outbox, Fase 2) y difunde el evento."""

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Registra un consumidor idempotente para el tema ``topic``.

        El tema deriva del contexto del evento (Blueprint §10.3), p. ej. ``server.*``.
        """

    async def consume(self) -> None:
        """Procesa el outbox y los eventos pendientes."""
