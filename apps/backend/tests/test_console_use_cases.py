"""Tests de los use cases del módulo Console (Blueprint §3.8, §16.9)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerState
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.streaming import ConsoleOutputRouter, ConsoleSubscription
from app.modules.console.application.use_cases import (
    ConsoleDeps,
    GetBufferUseCase,
    SendCommandUseCase,
    SubscribeOutputUseCase,
)
from app.modules.console.domain.command import CommandPriority
from app.modules.console.domain.errors import (
    CommandRejectedError,
    ServerOfflineError,
    StdinWriteError,
)
from app.modules.console.domain.events import (
    CONSOLE_COMMAND_SENT,
    CONSOLE_OUTPUT_TOPIC,
    console_output,
)
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader, FakeSettings, FakeTime, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_view(
    server_id: str = "srv-1",
    state: ServerState = ServerState.RUNNING,
    runtime_id: str = "r1",
) -> ServerView:
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


class FailingRuntime(FakeRuntime):
    """Runtime cuyo stdin está roto (para CONSOLE.STDIN_WRITE)."""

    def send_stdin(self, runtime_id: str, data: str) -> None:
        del runtime_id, data
        raise RuntimeError("stdin cerrado")


def make_harness(
    views: dict[str, ServerView] | None = None,
    runtime: FakeRuntime | None = None,
) -> tuple[
    SendCommandUseCase,
    GetBufferUseCase,
    SubscribeOutputUseCase,
    InProcessEventBus,
    FakeRuntime,
    InMemoryConsoleLogStore,
    ConsoleDeps,
    ConsoleOutputRouter,
]:
    bus = InProcessEventBus()
    runtime = runtime or FakeRuntime()
    store = InMemoryConsoleLogStore(max_lines=1000)
    deps = ConsoleDeps(
        server=FakeServerReader(views=views),
        runtime=runtime,
        bus=bus,
        time=FakeTime(NOW),
        settings=FakeSettings(),
        ids=SequenceIds("sub-1", "sub-2", "sub-3"),
        store=store,
    )
    queue = CommandQueue(runtime=runtime, bus=bus, time=FakeTime(NOW))
    router = ConsoleOutputRouter(store=store, bus=bus)
    bus.subscribe(CONSOLE_OUTPUT_TOPIC, router.on_output)
    send = SendCommandUseCase(deps, queue)
    get_buffer = GetBufferUseCase(deps)
    subscribe = SubscribeOutputUseCase(deps, router)
    return send, get_buffer, subscribe, bus, runtime, store, deps, router


# -- send_command ----------------------------------------------------------


async def test_send_command_escribe_stdin_y_publica_acuse() -> None:
    send, _, _, bus, runtime, _, _, _ = make_harness(views={"srv-1": make_view()})
    events: list[DomainEvent] = []
    bus.subscribe("console.command_sent", events.append)

    ack = await send.execute(SendCommand(server_id="srv-1", command="say hola"))

    assert ack.server_id == "srv-1"
    assert ack.command == "say hola"
    assert ack.priority is CommandPriority.NORMAL
    assert ack.seq == 0
    assert runtime.stdin_writes == [("r1", "say hola\n")]
    assert events[0].type == CONSOLE_COMMAND_SENT
    assert events[0].server_id == "srv-1"
    assert events[0].payload["command"] == "say hola"
    assert events[0].payload["priority"] == "normal"


async def test_send_command_servidor_detenido_rechazado() -> None:
    send, _, _, _, _, _, _, _ = make_harness(views={"srv-1": make_view(state=ServerState.STOPPED)})
    with pytest.raises(ServerOfflineError):
        await send.execute(SendCommand(server_id="srv-1", command="say hola"))


async def test_send_command_servidor_desconocido_rechazado() -> None:
    send, _, _, _, runtime, _, _, _ = make_harness(views={})
    with pytest.raises(ServerOfflineError):
        await send.execute(SendCommand(server_id="srv-x", command="say hola"))
    assert runtime.stdin_writes == []


async def test_send_command_vacio_rechazado() -> None:
    send, _, _, _, runtime, _, _, _ = make_harness(views={"srv-1": make_view()})
    with pytest.raises(CommandRejectedError):
        await send.execute(SendCommand(server_id="srv-1", command="   "))
    assert runtime.stdin_writes == []


async def test_prioridad_high_salta_por_delante_de_normal() -> None:
    send, _, _, _, runtime, _, _, _ = make_harness(views={"srv-1": make_view()})
    normal = asyncio.create_task(
        send.execute(
            SendCommand(server_id="srv-1", command="normal", priority=CommandPriority.NORMAL)
        )
    )
    urgent = asyncio.create_task(
        send.execute(
            SendCommand(server_id="srv-1", command="urgente", priority=CommandPriority.HIGH)
        )
    )
    ack_normal, ack_urgent = await asyncio.gather(normal, urgent)

    assert [write[1] for write in runtime.stdin_writes] == ["urgente\n", "normal\n"]
    assert ack_urgent.seq == 1
    assert ack_normal.seq == 0


async def test_suscripciones_concurrentes_serializadas_sin_intercalar() -> None:
    send, _, _, _, runtime, _, _, _ = make_harness(views={"srv-1": make_view()})
    first = asyncio.create_task(send.execute(SendCommand(server_id="srv-1", command="a")))
    second = asyncio.create_task(send.execute(SendCommand(server_id="srv-1", command="b")))
    ack_a, ack_b = await asyncio.gather(first, second)

    assert [write[1] for write in runtime.stdin_writes] == ["a\n", "b\n"]
    assert ack_a.seq == 0
    assert ack_b.seq == 1


async def test_fallo_de_escritura_stdin_se_normaliza() -> None:
    send, _, _, _, _, _, _, _ = make_harness(views={"srv-1": make_view()}, runtime=FailingRuntime())
    with pytest.raises(StdinWriteError):
        await send.execute(SendCommand(server_id="srv-1", command="say hola"))


# -- get_buffer -------------------------------------------------------------


async def test_get_buffer_devuelve_cola_y_marcador_de_agua() -> None:
    _, get_buffer, _, _, _, store, _, _ = make_harness()
    log = await store.get("srv-1")
    log.append("a")
    log.append("b")
    log.append("c")

    view = await get_buffer.execute("srv-1")
    assert view.high_water_mark == 2
    assert [line.line for line in view.lines] == ["a", "b", "c"]

    tail = await get_buffer.execute("srv-1", count=2)
    assert [line.line for line in tail.lines] == ["b", "c"]


async def test_get_buffer_servidor_sin_logs_devuelve_vacio() -> None:
    _, get_buffer, _, _, _, _, _, _ = make_harness()
    view = await get_buffer.execute("srv-otro")
    assert view.high_water_mark == -1
    assert view.lines == []


# -- subscribe --------------------------------------------------------------


async def test_subscribe_reproduce_buffer_y_sigue_en_vivo() -> None:
    _, _, subscribe, bus, _, store, _, _ = make_harness()
    log = await store.get("srv-1")
    log.append("pasada-1")
    log.append("pasada-2")

    sub = await subscribe.execute("srv-1", after_seq=0)
    await bus.publish(console_output("srv-1", "nueva-3", 3))

    lines: list[str] = []
    async for line in sub.stream():
        lines.append(line.line)
        if len(lines) == 2:
            break

    assert lines == ["pasada-2", "nueva-3"]


async def test_subscribe_idempotente_mismo_cursor() -> None:
    _, _, subscribe, bus, _, store, _, _ = make_harness()
    log = await store.get("srv-1")
    log.append("l0")
    log.append("l1")
    log.append("l2")

    sub_a = await subscribe.execute("srv-1", after_seq=1)
    sub_b = await subscribe.execute("srv-1", after_seq=1)
    await bus.publish(console_output("srv-1", "l3", 3))

    async def collect(sub: ConsoleSubscription) -> list[str]:
        lines = []
        async for line in sub.stream():
            lines.append(line.line)
            if len(lines) == 2:
                break
        return lines

    assert await collect(sub_a) == ["l2", "l3"]
    assert await collect(sub_b) == ["l2", "l3"]
