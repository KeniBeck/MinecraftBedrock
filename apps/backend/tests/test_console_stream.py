"""Tests del adaptador de streaming (runtime → buffer + CONSOLE.OUTPUT, §5.2)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.modules.console.domain.errors import ConsoleUnavailableError
from app.modules.console.domain.events import CONSOLE_OUTPUT_TOPIC
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.console.infrastructure.stream import ConsoleLogStream
from tests.conftest import FakeRuntime


def test_iter_lines_separa_trozos_y_normaliza() -> None:
    stream: Iterator[bytes] = iter([b"linea", b" uno\nlinea dos\r\n", b"linea tres"])

    lines = list(ConsoleLogStream._iter_lines(stream))

    assert lines == ["linea uno", "linea dos", "linea tres"]


def test_iter_lines_ignora_lineas_vacias() -> None:
    stream: Iterator[bytes] = iter([b"\n\n", b"  \n", b"ok\n"])

    lines = list(ConsoleLogStream._iter_lines(stream))

    assert lines == ["ok"]


def test_iter_lines_stream_vacio() -> None:
    assert list(ConsoleLogStream._iter_lines(iter([]))) == []


async def test_consume_vuelca_al_buffer_y_publica_cada_linea() -> None:
    bus = InProcessEventBus()
    events: list[DomainEvent] = []
    bus.subscribe(CONSOLE_OUTPUT_TOPIC, events.append)
    runtime = FakeRuntime()
    runtime.log_lines = [b"a\nb\n"]
    store = InMemoryConsoleLogStore(max_lines=1000)
    stream = ConsoleLogStream(runtime=runtime, store=store, bus=bus)

    await stream.consume("srv-1", "r1")

    log = await store.get("srv-1")
    assert log.high_water_mark == 1
    assert [line.line for line in log.tail()] == ["a", "b"]
    assert [event.payload["seq"] for event in events] == [0, 1]
    assert events[0].payload["line"] == "a"
    assert events[0].server_id == "srv-1"


async def test_consume_sin_runtime_lanza_unavailable() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    store = InMemoryConsoleLogStore()
    stream = ConsoleLogStream(runtime=runtime, store=store, bus=bus)

    with pytest.raises(ConsoleUnavailableError):
        await stream.consume("srv-1", None)

    log = await store.get("srv-1")
    assert log.high_water_mark == -1


async def test_consume_emite_un_evento_por_linea_no_por_chunk() -> None:
    bus = InProcessEventBus()
    events: list[DomainEvent] = []
    bus.subscribe(CONSOLE_OUTPUT_TOPIC, events.append)
    runtime = FakeRuntime()
    runtime.log_lines = [b"x\ny\nz"]
    store = InMemoryConsoleLogStore()
    stream = ConsoleLogStream(runtime=runtime, store=store, bus=bus)

    await stream.consume("srv-1", "r1")

    assert [event.payload["line"] for event in events] == ["x", "y", "z"]
    assert [event.payload["seq"] for event in events] == [0, 1, 2]
