"""Tests del boundary asíncrono del streaming en vivo (change-log §20).

Verifica que ``ConsoleLogStream.consume`` lee el iterador bloqueante del
runtime en un hilo worker: el event loop no se bloquea mientras el stream está
en espera, la cancelación no cuelga el loop (el hilo sale cuando el stream se
agota, como al detenerse el contenedor) y los errores del runtime se propagan.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Iterator

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.modules.console.domain.events import CONSOLE_OUTPUT_TOPIC
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.console.infrastructure.stream import ConsoleLogStream
from tests.conftest import FakeRuntime


class BlockingRuntime(FakeRuntime):
    """``stream_logs`` devuelve un generador que bloquea como el socket de Docker.

    ``reader_started`` se activa cuando el hilo de lectura ya entró en el
    generador (stream en espera del siguiente byte); ``stream_stopped`` simula
    el cierre de la conexión al parar el contenedor; ``reader_exited`` se
    activa cuando el generador termina (el hilo sale).
    """

    def __init__(self) -> None:
        super().__init__()
        self.reader_started = threading.Event()
        self.stream_stopped = threading.Event()
        self.reader_exited = threading.Event()

    def stream_logs(self, runtime_id: str) -> Iterator[bytes]:
        del runtime_id

        def gen() -> Iterator[bytes]:
            try:
                yield b"primera\n"
                self.reader_started.set()
                self.stream_stopped.wait()
                yield b"ultima\n"
            finally:
                self.reader_exited.set()

        return gen()


class ExplodingRuntime(FakeRuntime):
    """``stream_logs`` falla al arrancar (p. ej. contenedor eliminado)."""

    def stream_logs(self, runtime_id: str) -> Iterator[bytes]:
        del runtime_id
        raise RuntimeError("stream roto")


async def _wait_until(condition: Callable[[], bool], timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if condition():
            return
        await asyncio.sleep(0)
    raise AssertionError("condición no alcanzada a tiempo")


async def test_consume_no_bloquea_el_event_loop() -> None:
    bus = InProcessEventBus()
    events: list[DomainEvent] = []
    bus.subscribe(CONSOLE_OUTPUT_TOPIC, events.append)
    runtime = BlockingRuntime()
    store = InMemoryConsoleLogStore()
    stream = ConsoleLogStream(runtime=runtime, store=store, bus=bus)

    consume_task = asyncio.create_task(stream.consume("srv-1", "r1"))
    await asyncio.to_thread(runtime.reader_started.wait)
    await _wait_until(lambda: len(events) == 1)
    assert events[0].payload["line"] == "primera"

    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        for _ in range(5):
            ticks += 1
            await asyncio.sleep(0.02)

    await asyncio.wait_for(ticker(), timeout=1)
    assert ticks >= 5

    runtime.stream_stopped.set()
    await asyncio.wait_for(consume_task, timeout=2)
    assert events[-1].payload["line"] == "ultima"


async def test_cancelar_detiene_la_lectura_sin_colgarse() -> None:
    runtime = BlockingRuntime()
    stream = ConsoleLogStream(
        runtime=runtime,
        store=InMemoryConsoleLogStore(),
        bus=InProcessEventBus(),
    )

    consume_task = asyncio.create_task(stream.consume("srv-1", "r1"))
    await asyncio.to_thread(runtime.reader_started.wait)

    consume_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(consume_task, timeout=2)

    # El hilo no se puede interrumpir a la fuerza mientras el generador espera
    # I/O; sale solo cuando el stream se agota (Docker cierra la conexión al
    # detenerse el contenedor).
    runtime.stream_stopped.set()
    await asyncio.to_thread(runtime.reader_exited.wait)
    assert runtime.reader_exited.is_set()


async def test_consume_propaga_errores_del_runtime() -> None:
    runtime = ExplodingRuntime()
    stream = ConsoleLogStream(
        runtime=runtime,
        store=InMemoryConsoleLogStore(),
        bus=InProcessEventBus(),
    )

    with pytest.raises(RuntimeError, match="stream roto"):
        await stream.consume("srv-1", "r1")
