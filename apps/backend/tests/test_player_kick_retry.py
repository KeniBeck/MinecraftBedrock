"""Tests del kick con reintento (race "Player connected" → "Player Spawned").

BDS tarda ~5s entre ``Player connected`` y ``Player Spawned``; en esa ventana
el jugador no es un target válido y el kick falla con "No targets matched
selector". ``kick_with_retry`` observa la salida posterior a cada envío y
reintenta con backoff hasta confirmar éxito o agotar intentos (detectado en
prueba manual real, no en tests). Cubre el reintento vía ``BanEnforcementHandler``
(PLAYER.JOINED) y el agotamiento de intentos con log estructurado.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.results import CommandAck, ConsoleObservation
from app.modules.player.application import use_cases as player_use_cases
from app.modules.player.application.facade import PlayerFacade
from app.modules.player.application.use_cases import PlayerDeps
from app.modules.player.domain.bans import GlobalBan
from app.modules.player.domain.events import PLAYER_JOINED
from app.modules.player.domain.session import PlaySession, SessionEndReason
from app.modules.player.infrastructure.memory import (
    InMemoryPlayerBanRepository,
    InMemoryPlayerRepository,
)
from tests.conftest import FakeSettings, FakeTime, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
XUID = "2535467050498296"


class ScriptedConsole(ConsoleFacade):
    """``ConsoleFacade`` con ``send_command_and_observe`` guionizado.

    Cada llamada devuelve el siguiente juego de líneas del guion: ``()`` = salida
    sin error (kick confirmado), ``("No targets matched selector",)`` = error de
    target de BDS (kick fallido → reintentar).
    """

    def __init__(
        self,
        script: list[tuple[str, ...]],
        *,
        on_after_first: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._script = list(script)
        self._on_after_first = on_after_first
        self.sent: list[str] = []

    async def send_command_and_observe(
        self,
        cmd: SendCommand,
        *,
        window_s: float,
    ) -> ConsoleObservation:
        del window_s
        self.sent.append(cmd.command)
        if len(self.sent) == 1 and self._on_after_first is not None:
            await self._on_after_first()
        lines = self._script.pop(0) if self._script else ()
        ack = CommandAck(
            server_id=cmd.server_id,
            command=cmd.command,
            priority=cmd.priority,
            seq=len(self.sent),
            at=NOW,
        )
        return ConsoleObservation(ack=ack, lines=lines)


class Harness:
    """PlayerFacade con consola guionizada (controla la salida de BDS)."""

    def __init__(self, console: ScriptedConsole) -> None:
        self.bus = InProcessEventBus()
        self.time = FakeTime(NOW)
        self.console = console
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

    async def join(self, server_id: str, name: str, xuid: str) -> None:
        await self.bus.publish(
            DomainEvent(
                type=PLAYER_JOINED,
                server_id=server_id,
                payload={"server_id": server_id, "name": name, "xuid": xuid},
            )
        )
        await self.facade.await_ban_enforcement()


@pytest.fixture(autouse=True)
def _backoff_rapido(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backoff mínimo para que los reintentos no duerman en los tests."""
    monkeypatch.setattr(player_use_cases, "KICK_RETRY_BACKOFF_SECONDS", (0.001,) * 5)


async def test_enforcement_reintenta_y_confirma_en_segundo_intento() -> None:
    """PLAYER.JOINED → primer kick falla (error de target), segundo confirma."""
    console = ScriptedConsole(
        [
            ("No targets matched selector",),
            ("Kicked Steve from the game",),
        ]
    )
    harness = Harness(console)
    await harness.ban_repo.save_global_ban(
        GlobalBan(
            id="gb-1",
            xuid=XUID,
            gamertag="Steve",
            reason="spam",
            banned_by="admin-1",
            created_at=NOW,
        )
    )

    await harness.join("srv-1", "Steve", XUID)

    assert console.sent == ["kick Steve spam", "kick Steve spam"]


async def test_enforcement_no_reintenta_sin_error_en_la_salida() -> None:
    """Primer intento con salida limpia → un solo kick, sin reintentos."""
    console = ScriptedConsole([("Kicked Steve from the game",)])
    harness = Harness(console)
    await harness.ban_repo.save_global_ban(
        GlobalBan(
            id="gb-1",
            xuid=XUID,
            gamertag="Steve",
            reason="spam",
            banned_by="admin-1",
            created_at=NOW,
        )
    )

    await harness.join("srv-1", "Steve", XUID)

    assert console.sent == ["kick Steve spam"]


async def test_enforcement_agota_intentos_y_loguea_fallo(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Todos los intentos fallan → tope de ``KICK_MAX_ATTEMPTS``, se loguea el fallo."""
    console = ScriptedConsole([("No targets matched selector",)] * 3)
    harness = Harness(console)
    await harness.ban_repo.save_global_ban(
        GlobalBan(
            id="gb-1",
            xuid=XUID,
            gamertag="Steve",
            reason="spam",
            banned_by="admin-1",
            created_at=NOW,
        )
    )

    with caplog.at_level(logging.WARNING, logger="app.modules.player.application.use_cases"):
        await harness.join("srv-1", "Steve", XUID)

    assert len(console.sent) == 3
    assert "player.ban_kick_failed" in caplog.text


async def test_enforcement_corta_el_retry_si_el_jugador_se_desconecta() -> None:
    """El jugador se desconecta tras el primer fallo → se corta, no se reintenta."""
    captured: list[PlayerFacade] = []

    async def _desconectar() -> None:
        repository = captured[0].deps.repository
        session = await repository.get_open_session("srv-1", XUID)
        assert session is not None
        await repository.save_session(
            PlaySession(
                id=session.id,
                server_id=session.server_id,
                xuid=session.xuid,
                joined_at=session.joined_at,
                left_at=NOW,
                reason=SessionEndReason.LEFT,
                playtime_seconds=0,
            )
        )

    console = ScriptedConsole(
        [("No targets matched selector",)] * 5,
        on_after_first=_desconectar,
    )
    harness = Harness(console)
    captured.append(harness.facade)
    await harness.ban_repo.save_global_ban(
        GlobalBan(
            id="gb-1",
            xuid=XUID,
            gamertag="Steve",
            reason="spam",
            banned_by="admin-1",
            created_at=NOW,
        )
    )

    await harness.join("srv-1", "Steve", XUID)

    assert console.sent == ["kick Steve spam"]
