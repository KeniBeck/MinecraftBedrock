"""Bus en proceso (ADR-001): difusión síncrona en ``publish``.

Infraestructura compartida del pasillo de implementación (Fase B). Cumple
``EventBusPort``; ``consume`` es no-op porque no hay outbox todavía (Fase 2).
Los temas siguen el contexto del evento (Blueprint §10.3): ``server.*`` es
comodín de prefijo; ``config.changed`` es exacto.
"""

from __future__ import annotations

from inspect import isawaitable

from app.kernel.events.bus import EventHandler
from app.kernel.events.event import DomainEvent


class InProcessEventBus:
    """Bus en memoria con suscripción por tema (exacto o comodín ``*.``)."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscribers.setdefault(topic, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        topic = event.type.lower()
        for sub_topic, handlers in list(self._subscribers.items()):
            if not _matches(sub_topic, topic):
                continue
            for handler in handlers:
                result = handler(event)
                if isawaitable(result):
                    await result

    async def consume(self) -> None:
        # In-process: los eventos se entregan en publish; sin outbox (Fase 2).
        return None


def _matches(subscription: str, topic: str) -> bool:
    if subscription.endswith(".*"):
        return topic.startswith(subscription[:-1])
    return subscription == topic
