"""Reproducción del self-deadlock de enforcement detectado en prueba real.

En producción el enforcement corre inline dentro de la cadena de
``bus.publish(console_output(...))`` de ``ConsoleLogStream.consume`` (el
``PLAYER.JOINED`` lo publica ``PlayerJoinDetector``, que es un handler de
``CONSOLE.OUTPUT``). Cuando ``send_command_and_observe`` espera la respuesta del
kick en su ventana de observación, el consumidor del stream está bloqueado en el
mismo ``bus.publish`` y **no puede leer la respuesta desde la cola del worker**:
la ventana siempre queda vacía → ``_kick_output_failed`` siempre False →
"confirmed" → sin reintento.

Este test cablea el flujo real (stream task + router + detector + enforcement) y
verifica que el enforcement **observa el error de BDS y reintenta** (≥2 kicks).
Antes del fix (enforcement inline) solo se envía 1 kick y se loguea "confirmed";
después del fix (enforcement en task de fondo) se reintenta hasta agotar.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.infrastructure.parsers.player_join_detector import PlayerJoinDetector
from app.kernel.ports.runtime import ServerState
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.streaming import ConsoleOutputRouter
from app.modules.console.application.use_cases import ConsoleDeps
from app.modules.console.domain.events import CONSOLE_OUTPUT_TOPIC
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.console.infrastructure.stream import ConsoleLogStream
from app.modules.player.application import use_cases as player_use_cases
from app.modules.player.application.facade import PlayerFacade
from app.modules.player.application.use_cases import PlayerDeps
from app.modules.player.domain.bans import GlobalBan
from app.modules.player.infrastructure.memory import (
    InMemoryPlayerBanRepository,
    InMemoryPlayerRepository,
)
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader, FakeSettings, FakeTime, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
XUID = "2535467050498296"
NAME = "Steve"


class ReactiveRuntime(FakeRuntime):
    """``stream_logs``: línea de join, luego un error de target por cada kick.

    Emula a BDS: al escribir un ``kick`` en stdin, responde
    ``No targets matched selector`` (el jugador aún no ha spawnado).
    """

    def __init__(self) -> None:
        super().__init__()
        self._kick_sent = threading.Event()

    def send_stdin(self, runtime_id: str, data: str) -> None:
        super().send_stdin(runtime_id, data)
        if data.strip().startswith("kick "):
            self._kick_sent.set()

    def stream_logs(self, runtime_id: str) -> Iterator[bytes]:
        del runtime_id

        def gen() -> Iterator[bytes]:
            yield f"Player connected: {NAME}, xuid: {XUID}\n".encode()
            while True:
                self._kick_sent.wait(timeout=5.0)
                self._kick_sent.clear()
                yield b"No targets matched selector\n"

        return gen()


class Harness:
    """Cableado idéntico al de producción: stream + router + detector + facade."""

    def __init__(self) -> None:
        self.bus = InProcessEventBus()
        self.time = FakeTime(NOW)
        self.runtime = ReactiveRuntime()
        self.store = InMemoryConsoleLogStore()
        view = ServerView(
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
        console_deps = ConsoleDeps(
            server=FakeServerReader(views={"srv-1": view}),
            runtime=self.runtime,
            bus=self.bus,
            time=self.time,
            settings=FakeSettings(),
            ids=SequenceIds("sub-1"),
            store=self.store,
        )
        queue = CommandQueue(runtime=self.runtime, bus=self.bus, time=self.time)
        router = ConsoleOutputRouter(store=self.store, bus=self.bus)
        console = ConsoleFacade(deps=console_deps, queue=queue, router=router)
        console.register_handlers()
        detector = PlayerJoinDetector(bus=self.bus)
        self.bus.subscribe(CONSOLE_OUTPUT_TOPIC, detector)
        self.ban_repo = InMemoryPlayerBanRepository()
        deps = PlayerDeps(
            repository=InMemoryPlayerRepository(),
            ban_repository=self.ban_repo,
            console=console,
            bus=self.bus,
            ids=SequenceIds("s-1"),
            time=self.time,
            settings=FakeSettings(),
        )
        self.facade = PlayerFacade(deps)
        self.facade.register_handlers()
        self.stream = ConsoleLogStream(runtime=self.runtime, store=self.store, bus=self.bus)


def _kick_count(runtime: FakeRuntime) -> int:
    return len([d for _, d in runtime.stdin_writes if d.startswith("kick ")])


async def _wait_kicks(runtime: FakeRuntime, count: int, timeout: float = 3.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if _kick_count(runtime) >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"no se alcanzaron {count} kick(s) a tiempo")


@pytest.fixture(autouse=True)
def _kick_retry_rapido(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ventana/backoff mínimos para un test rápido y determinista."""
    monkeypatch.setattr(player_use_cases, "KICK_RETRY_BACKOFF_SECONDS", (0.001,) * 5)
    monkeypatch.setattr(player_use_cases, "KICK_OBSERVE_WINDOW_SECONDS", 0.05)


async def test_kick_observa_el_error_y_reintenta_con_stream_real() -> None:
    harness = Harness()
    await harness.ban_repo.save_global_ban(
        GlobalBan(
            id="gb-1",
            xuid=XUID,
            gamertag=NAME,
            reason="spam",
            banned_by="admin-1",
            created_at=NOW,
        )
    )
    consume_task = asyncio.create_task(harness.stream.consume("srv-1", "r1"))
    try:
        await _wait_kicks(harness.runtime, 2)
        await harness.facade.await_ban_enforcement()
        assert _kick_count(harness.runtime) >= 2
    finally:
        consume_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consume_task


async def test_kick_agota_intentos_y_loguea_fallo_con_stream_real(
    caplog: pytest.LogCaptureFixture,
) -> None:
    harness = Harness()
    await harness.ban_repo.save_global_ban(
        GlobalBan(
            id="gb-1",
            xuid=XUID,
            gamertag=NAME,
            reason="spam",
            banned_by="admin-1",
            created_at=NOW,
        )
    )
    consume_task = asyncio.create_task(harness.stream.consume("srv-1", "r1"))
    try:
        with caplog.at_level(logging.WARNING, logger="app.modules.player.application.use_cases"):
            await _wait_kicks(harness.runtime, 3)
            await harness.facade.await_ban_enforcement()
        assert "player.ban_kick_failed" in caplog.text
    finally:
        consume_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consume_task
