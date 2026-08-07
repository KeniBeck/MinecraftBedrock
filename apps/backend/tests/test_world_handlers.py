"""Tests de los handlers del módulo World (Fase E paso 12).

World solo consume ``SERVER.VERSION_CHANGED`` por consistencia (decisión §22):
los handlers son defensivos, nunca cortan el bus.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.modules.world.application.facade import WorldFacade
from app.modules.world.application.handlers import (
    SERVER_VERSION_CHANGED_TOPIC,
    VersionChangedHandler,
)


async def test_version_changed_con_payload_valido_no_rompe() -> None:
    handler = VersionChangedHandler()
    await handler(
        DomainEvent(
            type="SERVER.VERSION_CHANGED",
            server_id="srv-1",
            payload={"server_id": "srv-1", "version": "1.26.40.8"},
        )
    )


async def test_version_changed_con_payload_invalido_se_ignora() -> None:
    handler = VersionChangedHandler()
    await handler(DomainEvent(type="SERVER.VERSION_CHANGED", payload={}))
    await handler(
        DomainEvent(
            type="SERVER.VERSION_CHANGED",
            server_id="srv-1",
            payload={"version": 123},
        )
    )


async def test_register_handlers_suscribe_el_tema_version_changed() -> None:
    bus = InProcessEventBus()
    facade = WorldFacade(SimpleNamespace(bus=bus))  # type: ignore[arg-type]
    facade.register_handlers()

    events: list[DomainEvent] = []
    bus.subscribe(SERVER_VERSION_CHANGED_TOPIC, events.append)
    await bus.publish(
        DomainEvent(
            type="SERVER.VERSION_CHANGED",
            server_id="srv-1",
            payload={"server_id": "srv-1", "version": "1.26.40.8"},
        )
    )

    assert events
