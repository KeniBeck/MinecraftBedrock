"""Tests de la reconciliación de streams al arrancar el panel.

``ConsoleStreamReconciler`` arranca los streams de los servidores persistidos
como ``running`` solo si el contenedor real sigue corriendo. Si el contenedor ya
no corre, no fuerza nada (lo reconcilia el poller de Monitoreo).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.bus import EventBusPort
from app.kernel.ports.runtime import RuntimeState, ServerRuntimePort, ServerState
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.console.infrastructure.reconcile import ConsoleStreamReconciler
from app.modules.console.infrastructure.store import ConsoleLogWriter
from app.modules.console.infrastructure.stream import ConsoleLogStream
from app.modules.console.infrastructure.stream_manager import ConsoleStreamManager
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class BlockingStream(ConsoleLogStream):
    """``consume`` en curso hasta cancelarse; observa la tarea viva."""

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


def make_view(server_id: str, state: ServerState, runtime_id: str | None = "r1") -> ServerView:
    return ServerView(
        id=server_id,
        name="Survival",
        state=state,
        version="1.20.0",
        image_ref="img:latest",
        runtime_id=runtime_id,
        created_at=NOW,
        updated_at=NOW,
        connection=stub_connection(),
    )


def make_reconciler(
    views: dict[str, ServerView],
    runtime: FakeRuntime,
) -> tuple[ConsoleStreamReconciler, ConsoleStreamManager]:
    bus = InProcessEventBus()
    store = InMemoryConsoleLogStore()
    stream = BlockingStream(runtime=runtime, store=store, bus=bus)
    server = FakeServerReader(views)
    manager = ConsoleStreamManager(stream=stream, server=server, bus=bus)
    manager.subscribe()
    reconciler = ConsoleStreamReconciler(manager=manager, server=server, runtime=runtime)
    return reconciler, manager


async def test_reconcile_arranca_stream_de_servidor_running(
    runtime: FakeRuntime,
) -> None:
    runtime.states["r1"] = RuntimeState.RUNNING
    reconciler, manager = make_reconciler(
        {"srv-1": make_view("srv-1", ServerState.RUNNING)},
        runtime,
    )

    await reconciler.reconcile()

    assert manager.active("srv-1")


async def test_reconcile_no_arranca_si_contenedor_no_corre(runtime: FakeRuntime) -> None:
    runtime.states["r1"] = RuntimeState.STOPPED
    reconciler, manager = make_reconciler(
        {"srv-1": make_view("srv-1", ServerState.RUNNING)},
        runtime,
    )

    await reconciler.reconcile()

    assert not manager.active("srv-1")


async def test_reconcile_ignora_servidores_no_running(
    runtime: FakeRuntime,
) -> None:
    runtime.states["r1"] = RuntimeState.RUNNING
    runtime.states["r2"] = RuntimeState.RUNNING
    reconciler, manager = make_reconciler(
        {
            "srv-1": make_view("srv-1", ServerState.RUNNING),
            "srv-2": make_view("srv-2", ServerState.STOPPED),
        },
        runtime,
    )

    await reconciler.reconcile()

    assert manager.active("srv-1")
    assert not manager.active("srv-2")


async def test_reconcile_es_idempotente_si_stream_ya_activo(
    runtime: FakeRuntime,
) -> None:
    runtime.states["r1"] = RuntimeState.RUNNING
    reconciler, manager = make_reconciler(
        {"srv-1": make_view("srv-1", ServerState.RUNNING)},
        runtime,
    )
    await reconciler.reconcile()

    await reconciler.reconcile()

    assert manager.active("srv-1")
    assert len(manager._tasks) == 1
