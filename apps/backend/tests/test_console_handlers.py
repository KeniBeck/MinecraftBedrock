"""Tests de los handlers del módulo Console (TASK.STARTED, parsers §7.3)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.infrastructure.events.bus import InProcessEventBus
from app.infrastructure.parsers.save_detector import SaveDetector
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerState
from app.modules.console.application.handlers import TaskStartedHandler
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.use_cases import (
    ConsoleDeps,
    SendCommandUseCase,
)
from app.modules.console.domain.events import (
    CONSOLE_OUTPUT_TOPIC,
    TASK_STARTED_TOPIC,
    WORLD_SAVED,
    WORLD_SAVED_TOPIC,
    console_output,
)
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader, FakeSettings, FakeTime, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_sender(
    bus: InProcessEventBus,
    runtime: FakeRuntime,
) -> SendCommandUseCase:
    deps = ConsoleDeps(
        server=FakeServerReader(
            views={
                "srv-1": ServerView(
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
            }
        ),
        runtime=runtime,
        bus=bus,
        time=FakeTime(NOW),
        settings=FakeSettings(),
        ids=SequenceIds("sub-1"),
        store=InMemoryConsoleLogStore(),
    )
    queue = CommandQueue(runtime=runtime, bus=bus, time=FakeTime(NOW))
    return SendCommandUseCase(deps, queue)


async def test_task_started_envia_comandos_programados() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    bus.subscribe(TASK_STARTED_TOPIC, TaskStartedHandler(make_sender(bus, runtime)))

    await bus.publish(
        DomainEvent(
            type="TASK.STARTED",
            server_id="srv-1",
            payload={"task_id": "t-1", "commands": ["say inicio", "say fin"]},
        )
    )

    assert [write[1] for write in runtime.stdin_writes] == ["say inicio\n", "say fin\n"]


async def test_task_started_acepta_un_unico_command() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    bus.subscribe(TASK_STARTED_TOPIC, TaskStartedHandler(make_sender(bus, runtime)))

    await bus.publish(
        DomainEvent(
            type="TASK.STARTED",
            server_id="srv-1",
            payload={"command": "save hold"},
        )
    )

    assert runtime.stdin_writes == [("r1", "save hold\n")]


async def test_task_started_sin_server_id_se_ignora() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    bus.subscribe(TASK_STARTED_TOPIC, TaskStartedHandler(make_sender(bus, runtime)))

    await bus.publish(DomainEvent(type="TASK.STARTED", payload={"commands": ["save hold"]}))

    assert runtime.stdin_writes == []


async def test_task_started_sin_comandos_se_ignora() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    bus.subscribe(TASK_STARTED_TOPIC, TaskStartedHandler(make_sender(bus, runtime)))

    await bus.publish(DomainEvent(type="TASK.STARTED", server_id="srv-1", payload={}))

    assert runtime.stdin_writes == []


# -- parser declarativo: WORLD.SAVED ----------------------------------------


async def test_save_detector_publica_world_saved_en_linea_de_guardado() -> None:
    bus = InProcessEventBus()
    events: list[DomainEvent] = []
    bus.subscribe(WORLD_SAVED_TOPIC, events.append)
    detector = SaveDetector(bus=bus)
    bus.subscribe(CONSOLE_OUTPUT_TOPIC, detector)

    await bus.publish(console_output("srv-1", "Save complete.", 7))

    assert len(events) == 1
    assert events[0].type == WORLD_SAVED
    assert events[0].server_id == "srv-1"
    assert events[0].payload["line"] == "Save complete."


async def test_save_detector_ignora_lineas_no_relacionadas() -> None:
    bus = InProcessEventBus()
    events: list[DomainEvent] = []
    bus.subscribe(WORLD_SAVED_TOPIC, events.append)
    detector = SaveDetector(bus=bus)
    bus.subscribe(CONSOLE_OUTPUT_TOPIC, detector)

    await bus.publish(console_output("srv-1", "Player joined the game", 8))

    assert events == []


async def test_save_detector_no_confunde_comandos_save_hold_resume() -> None:
    bus = InProcessEventBus()
    events: list[DomainEvent] = []
    bus.subscribe(WORLD_SAVED_TOPIC, events.append)
    detector = SaveDetector(bus=bus)
    bus.subscribe(CONSOLE_OUTPUT_TOPIC, detector)

    await bus.publish(console_output("srv-1", "save hold", 1))
    await bus.publish(console_output("srv-1", "save resume", 2))

    assert events == []


async def test_save_detector_requiere_server_id() -> None:
    bus = InProcessEventBus()
    events: list[DomainEvent] = []
    bus.subscribe(WORLD_SAVED_TOPIC, events.append)
    detector = SaveDetector(bus=bus)
    bus.subscribe(CONSOLE_OUTPUT_TOPIC, detector)

    await bus.publish(console_output("", "Save complete.", 3))

    assert events == []
