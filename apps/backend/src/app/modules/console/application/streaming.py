"""Streaming de salida idempotente (Blueprint §16.9: 'streaming idempotente').

``ConsoleOutputRouter`` reparte ``CONSOLE.OUTPUT`` a las suscripciones activas
por servidor con backpressure (cola acotada; si está llena se descarta la línea
entrante, el cursor permite resincronizar). ``ConsoleSubscription`` ofrece un
async iterador que primero reproduce el buffer desde ``after_seq`` y luego
sigue en vivo.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass, field

from app.kernel.events.bus import EventBusPort
from app.kernel.events.event import DomainEvent
from app.modules.console.domain.console_log import ConsoleLine
from app.modules.console.domain.repository import ConsoleLogStorePort


@dataclass(slots=True)
class ConsoleSubscription:
    """Suscripción a la salida de un servidor (resume por cursor ``after_seq``)."""

    server_id: str
    subscriber_id: str
    after_seq: int
    high_water_mark: int
    store: ConsoleLogStorePort
    router: ConsoleOutputRouter
    queue: asyncio.Queue[ConsoleLine | None] = field(init=False)

    def __post_init__(self) -> None:
        self.queue = asyncio.Queue(maxsize=self.router.max_backlog)

    async def stream(self) -> AsyncIterator[ConsoleLine]:
        """Reproduce el buffer desde ``after_seq`` y luego líneas en vivo.

        La reproducción se acota al ``high_water_mark`` capturado al suscribirse
        para no duplicar líneas que llegan en vivo por el router.
        """
        log = await self.store.get(self.server_id)
        for line in log.since(self.after_seq):
            if line.seq > self.high_water_mark:
                break
            yield line
        while True:
            item = await self.queue.get()
            if item is None:
                break
            yield item

    async def close(self) -> None:
        """Cancela la suscripción y desbloquea al iterador (sentinel ``None``)."""
        self.router.unregister(self)
        with suppress(asyncio.QueueFull):
            self.queue.put_nowait(None)


class ConsoleOutputRouter:
    """Fan-out de ``CONSOLE.OUTPUT`` a las suscripciones activas."""

    def __init__(
        self,
        store: ConsoleLogStorePort,
        bus: EventBusPort,
        *,
        max_backlog: int = 200,
    ) -> None:
        self._store = store
        self._bus = bus
        self.max_backlog = max_backlog
        self._subscriptions: dict[tuple[str, str], ConsoleSubscription] = {}

    async def subscribe(
        self,
        server_id: str,
        *,
        after_seq: int | None = None,
        subscriber_id: str,
    ) -> ConsoleSubscription:
        """Crea una suscripción con cursor de reanudación idempotente.

        Se captura el ``high_water_mark`` antes de registrar la suscripción:
        las líneas ya presentes en el buffer se reproducen; las posteriores
        llegan en vivo. Un consumidor lento solo pierde líneas si satura el
        backlog; puede reanudar con un ``after_seq`` mayor.
        """
        log = await self._store.get(server_id)
        cursor = after_seq if after_seq is not None else log.high_water_mark
        subscription = ConsoleSubscription(
            server_id=server_id,
            subscriber_id=subscriber_id,
            after_seq=cursor,
            high_water_mark=log.high_water_mark,
            store=self._store,
            router=self,
        )
        self._subscriptions[(server_id, subscriber_id)] = subscription
        return subscription

    def unregister(self, subscription: ConsoleSubscription) -> None:
        self._subscriptions.pop((subscription.server_id, subscription.subscriber_id), None)

    async def on_output(self, event: DomainEvent) -> None:
        """Handler del tema ``console.output``: fan-out por servidor."""
        server_id = event.server_id
        if not server_id:
            return
        seq = int(event.payload.get("seq", -1))
        line = str(event.payload.get("line", ""))
        for subscription in list(self._subscriptions.values()):
            if subscription.server_id != server_id:
                continue
            if seq <= subscription.high_water_mark:
                continue
            if subscription.queue.full():
                continue
            subscription.queue.put_nowait(ConsoleLine(seq=seq, server_id=server_id, line=line))
