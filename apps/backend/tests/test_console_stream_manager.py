"""Tests del ciclo de vida del stream de logs (§10 decisión 11, corrección).

Verifica que ``ConsoleStreamManager`` arranca la tarea de consumo en
``SERVER.STARTED``, la cancela en ``SERVER.STOPPED``/``SERVER.CRASHED``/
``SERVER.REMOVED``, no deja consumidores huérfanos y soporta varios servidores
a la vez (una tarea por ``server_id``).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.bus import EventBusPort
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerRuntimePort, ServerState
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.console.infrastructure.store import ConsoleLogWriter
from app.modules.console.infrastructure.stream import ConsoleLogStream
from app.modules.console.infrastructure.stream_manager import ConsoleStreamManager
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class BlockingStream(ConsoleLogStream):
    """``ConsoleLogStream`` cuyo ``consume`` queda en curso hasta cancelarse.

    Permite observar la tarea viva sin depender de un runtime real que
    bloquee: ``consume`` espera en un ``asyncio.Event`` hasta que el gestor la
    cancela.
    """

    def __init__(
        self,
        runtime: ServerRuntimePort,
        store: ConsoleLogWriter,
        bus: EventBusPort,
    ) -> None:
        super().__init__(runtime=runtime, store=store, bus=bus)
        self.release = asyncio.Event()

    async def consume(self, server_id: str, runtime_id: str | None) -> None:
        await self.release.wait()


def make_view(server_id: str, runtime_id: str | None = "r1") -> ServerView:
    return ServerView(
        id=server_id,
        name="Survival",
        state=ServerState.RUNNING,
        version="1.20.0",
        image_ref="img:latest",
        runtime_id=runtime_id,
        created_at=NOW,
        updated_at=NOW,
        connection=stub_connection(),
    )


def make_manager(
    views: dict[str, ServerView] | None = None,
) -> tuple[ConsoleStreamManager, InProcessEventBus, BlockingStream]:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    store = InMemoryConsoleLogStore()
    stream = BlockingStream(runtime=runtime, store=store, bus=bus)
    server = FakeServerReader(
        views=views
        if views is not None
        else {
            "srv-1": make_view("srv-1"),
            "srv-2": make_view("srv-2"),
        }
    )
    manager = ConsoleStreamManager(stream=stream, server=server, bus=bus)
    manager.subscribe()
    return manager, bus, stream


def started(server_id: str) -> DomainEvent:
    return DomainEvent(type="SERVER.STARTED", server_id=server_id)


def stopped(server_id: str) -> DomainEvent:
    return DomainEvent(type="SERVER.STOPPED", server_id=server_id)


async def test_server_started_arranca_el_stream() -> None:
    manager, bus, _ = make_manager()

    await bus.publish(started("srv-1"))

    assert manager.active("srv-1")


async def test_server_started_es_idempotente_si_ya_hay_stream() -> None:
    manager, bus, _ = make_manager()
    await bus.publish(started("srv-1"))

    await bus.publish(started("srv-1"))

    assert manager.active("srv-1")
    assert len(manager._tasks) == 1


async def test_server_started_sin_runtime_no_arranca() -> None:
    manager, bus, _ = make_manager(views={"srv-1": make_view("srv-1", None)})

    await bus.publish(started("srv-1"))

    assert not manager.active("srv-1")


async def test_server_started_con_servidor_desconocido_no_arranca() -> None:
    manager, bus, _ = make_manager(views={})

    await bus.publish(started("srv-1"))

    assert not manager.active("srv-1")


async def test_server_stopped_detiene_el_stream() -> None:
    manager, bus, _ = make_manager()
    await bus.publish(started("srv-1"))
    assert manager.active("srv-1")

    await bus.publish(stopped("srv-1"))

    assert not manager.active("srv-1")


async def test_server_crashed_detiene_el_stream() -> None:
    manager, bus, _ = make_manager()
    await bus.publish(started("srv-1"))
    assert manager.active("srv-1")

    await bus.publish(DomainEvent(type="SERVER.CRASHED", server_id="srv-1"))

    assert not manager.active("srv-1")


async def test_server_removed_detiene_el_stream_sin_consumidor_orfano() -> None:
    manager, bus, _ = make_manager()
    await bus.publish(started("srv-1"))
    assert manager.active("srv-1")

    await bus.publish(DomainEvent(type="SERVER.REMOVED", server_id="srv-1"))

    assert not manager.active("srv-1")
    assert manager._tasks == {}


async def test_stream_que_termina_solo_se_elimina_del_estado() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    runtime.log_lines = [b"x\n", b"y\n"]
    store = InMemoryConsoleLogStore()
    stream = ConsoleLogStream(runtime=runtime, store=store, bus=bus)
    server = FakeServerReader(views={"srv-1": make_view("srv-1")})
    manager = ConsoleStreamManager(stream=stream, server=server, bus=bus)
    manager.subscribe()

    await bus.publish(started("srv-1"))
    await manager._tasks["srv-1"]

    assert not manager.active("srv-1")
    assert manager._tasks == {}


async def test_evento_sin_server_id_no_hace_nada() -> None:
    manager, bus, _ = make_manager()

    await bus.publish(DomainEvent(type="SERVER.STARTED"))

    assert manager._tasks == {}


async def test_varios_servidores_conviven_y_se_paran_independientes() -> None:
    manager, bus, _ = make_manager()
    await bus.publish(started("srv-1"))
    await bus.publish(started("srv-2"))
    assert manager.active("srv-1")
    assert manager.active("srv-2")

    await bus.publish(stopped("srv-1"))

    assert not manager.active("srv-1")
    assert manager.active("srv-2")
