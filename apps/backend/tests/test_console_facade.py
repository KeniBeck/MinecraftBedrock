"""Tests end-to-end de la facade pública del módulo Console (Blueprint §3.8)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerState
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.streaming import ConsoleOutputRouter
from app.modules.console.application.use_cases import ConsoleDeps
from app.modules.console.domain.command import CommandPriority
from app.modules.console.domain.events import console_output
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader, FakeSettings, FakeTime, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_view() -> ServerView:
    return ServerView(
        id="srv-1",
        name="Survival",
        state=ServerState.RUNNING,
        version="1.20.0",
        image_ref="img:latest",
        runtime_id="r1",
        created_at=NOW,
        updated_at=NOW,
        connection=stub_connection(),
    )


def make_facade(
    views: dict[str, ServerView] | None = None,
) -> tuple[ConsoleFacade, InProcessEventBus, FakeRuntime, InMemoryConsoleLogStore]:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    store = InMemoryConsoleLogStore(max_lines=1000)
    deps = ConsoleDeps(
        server=FakeServerReader(views=views or {"srv-1": make_view()}),
        runtime=runtime,
        bus=bus,
        time=FakeTime(NOW),
        settings=FakeSettings(),
        ids=SequenceIds("sub-1"),
        store=store,
    )
    queue = CommandQueue(runtime=runtime, bus=bus, time=FakeTime(NOW))
    router = ConsoleOutputRouter(store=store, bus=bus)
    facade = ConsoleFacade(deps=deps, queue=queue, router=router)
    facade.register_handlers()
    return facade, bus, runtime, store


async def test_send_command_via_facade() -> None:
    facade, _, runtime, _ = make_facade()

    ack = await facade.send_command(
        SendCommand(server_id="srv-1", command="say hola", priority=CommandPriority.HIGH)
    )

    assert ack.priority is CommandPriority.HIGH
    assert runtime.stdin_writes == [("r1", "say hola\n")]


async def test_get_buffer_via_facade() -> None:
    facade, _, _, store = make_facade()
    log = await store.get("srv-1")
    log.append("a")
    log.append("b")

    view = await facade.get_buffer("srv-1")

    assert view.high_water_mark == 1
    assert [line.line for line in view.lines] == ["a", "b"]


async def test_subscribe_via_facade_recibe_en_vivo() -> None:
    facade, bus, _, store = make_facade()
    log = await store.get("srv-1")
    log.append("vieja-0")

    sub = await facade.subscribe("srv-1", after_seq=-1)
    await bus.publish(console_output("srv-1", "nueva-1", 1))

    lines: list[str] = []
    async for line in sub.stream():
        lines.append(line.line)
        if len(lines) == 2:
            break

    assert lines == ["vieja-0", "nueva-1"]


async def test_task_started_activa_la_facade() -> None:
    facade, bus, runtime, _ = make_facade()

    await bus.publish(
        DomainEvent(
            type="TASK.STARTED",
            server_id="srv-1",
            payload={"commands": ["save hold", "list"]},
        )
    )

    assert [write[1] for write in runtime.stdin_writes] == ["save hold\n", "list\n"]


async def test_console_output_difundido_a_las_suscripciones() -> None:
    facade, bus, _, _ = make_facade()
    sub = await facade.subscribe("srv-1", after_seq=0)

    await bus.publish(console_output("srv-1", "linea-live", 1))
    await bus.publish(console_output("srv-1", "linea-live-2", 2))

    lines: list[str] = []
    async for line in sub.stream():
        lines.append(line.line)
        if len(lines) == 2:
            break

    assert lines == ["linea-live", "linea-live-2"]
