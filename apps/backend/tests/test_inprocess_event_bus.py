"""Tests del ``InProcessEventBus`` (ADR-001: difusión en proceso)."""

from __future__ import annotations

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent


async def test_suscripcion_exacta() -> None:
    bus = InProcessEventBus()
    received: list[str] = []
    bus.subscribe("config.changed", lambda e: received.append(e.type))

    await bus.publish(DomainEvent(type="CONFIG.CHANGED"))

    assert received == ["CONFIG.CHANGED"]


async def test_comodin_de_prefijo() -> None:
    bus = InProcessEventBus()
    received: list[str] = []
    bus.subscribe("server.*", lambda e: received.append(e.type))

    await bus.publish(DomainEvent(type="SERVER.CREATED", server_id="s1"))
    await bus.publish(DomainEvent(type="SERVER.REMOVED", server_id="s1"))
    await bus.publish(DomainEvent(type="CONFIG.CHANGED"))

    assert received == ["SERVER.CREATED", "SERVER.REMOVED"]


async def test_handler_sync_y_async() -> None:
    bus = InProcessEventBus()
    sync_calls: list[str] = []
    async_calls: list[str] = []

    def sync(e: DomainEvent) -> None:
        sync_calls.append(e.type)

    async def async_handler(e: DomainEvent) -> None:
        async_calls.append(e.type)

    bus.subscribe("server.*", sync)
    bus.subscribe("server.*", async_handler)

    await bus.publish(DomainEvent(type="SERVER.STARTED", server_id="s1"))

    assert sync_calls == ["SERVER.STARTED"]
    assert async_calls == ["SERVER.STARTED"]


async def test_suscritor_que_no_corresponde_no_recibe() -> None:
    bus = InProcessEventBus()
    received: list[str] = []
    bus.subscribe("world.activated", lambda e: received.append(e.type))

    await bus.publish(DomainEvent(type="SERVER.CREATED", server_id="s1"))

    assert received == []


async def test_consume_es_noop_sin_outbox() -> None:
    bus = InProcessEventBus()
    await bus.consume()  # no-op sin outbox (ADR-001): no debe lanzar
