"""Tests del kick inmediato en el ban global (no esperar PLAYER.JOINED).

Un ban global se aplica mientras el jugador está conectado: ``PLAYER.JOINED``
no se dispara para quien ya está dentro, así que ``BanPlayerGloballyUseCase``
expulsa al instante de cada servidor donde haya sesión abierta. Si el jugador
está offline no hace nada y el enforcement por join cubrirá futuras entradas.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.results import CommandAck, ConsoleObservation
from app.modules.player.application.commands import BanPlayerGloballyCommand
from app.modules.player.application.facade import PlayerFacade
from app.modules.player.application.use_cases import PlayerDeps
from app.modules.player.domain.session import PlaySession
from app.modules.player.infrastructure.memory import (
    InMemoryPlayerBanRepository,
    InMemoryPlayerRepository,
)
from tests.conftest import FakeSettings, FakeTime, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
XUID = "2535467050498296"


class ScriptedConsole(ConsoleFacade):
    """``ConsoleFacade`` con ``send_command_and_observe`` guionizado."""

    def __init__(self, script: list[tuple[str, ...]]) -> None:
        self._script = list(script)
        self.sent: list[str] = []

    async def send_command_and_observe(
        self,
        cmd: SendCommand,
        *,
        window_s: float,
    ) -> ConsoleObservation:
        del window_s
        self.sent.append(cmd.command)
        lines = self._script.pop(0) if self._script else ()
        return ConsoleObservation(
            ack=CommandAck(
                server_id=cmd.server_id,
                command=cmd.command,
                priority=cmd.priority,
                seq=len(self.sent),
                at=NOW,
            ),
            lines=lines,
        )


class Harness:
    def __init__(self, console: ScriptedConsole) -> None:
        self.console = console
        self.repository = InMemoryPlayerRepository()
        self.ban_repo = InMemoryPlayerBanRepository()
        deps = PlayerDeps(
            repository=self.repository,
            ban_repository=self.ban_repo,
            console=console,
            bus=InProcessEventBus(),
            ids=SequenceIds("s-1"),
            time=FakeTime(NOW),
            settings=FakeSettings(),
        )
        self.facade = PlayerFacade(deps)
        self.facade.register_handlers()

    async def open_session(self, server_id: str) -> None:
        await self.repository.save_session(
            PlaySession(
                id=f"{server_id}-1",
                server_id=server_id,
                xuid=XUID,
                joined_at=NOW,
                left_at=None,
                reason=None,
                playtime_seconds=0,
            )
        )


@pytest.fixture(autouse=True)
def _backoff_rapido(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.player.application import use_cases as player_use_cases

    monkeypatch.setattr(player_use_cases, "KICK_RETRY_BACKOFF_SECONDS", (0.001,) * 5)


async def test_ban_global_con_sesion_abierta_expulsa_inmediato() -> None:
    """Jugador conectado en un servidor → el ban global lo expulsa al momento."""
    console = ScriptedConsole([("Kicked Steve from the game",)])
    harness = Harness(console)
    await harness.open_session("srv-1")

    await harness.facade.ban_globally(
        BanPlayerGloballyCommand(
            gamertag="Steve",
            xuid=XUID,
            reason="spam",
            actor_id="admin-1",
        )
    )

    assert console.sent == ["kick Steve spam"]


async def test_ban_global_expulsa_de_cada_servidor_conexion_abierta() -> None:
    """Con sesiones abiertas en varios servidores, expulsa de cada uno."""
    console = ScriptedConsole(
        [
            ("Kicked Steve from the game",),
            ("Kicked Steve from the game",),
        ]
    )
    harness = Harness(console)
    await harness.open_session("srv-1")
    await harness.open_session("srv-2")

    await harness.facade.ban_globally(
        BanPlayerGloballyCommand(
            gamertag="Steve",
            xuid=XUID,
            reason="spam",
            actor_id="admin-1",
        )
    )

    assert sorted(console.sent) == ["kick Steve spam", "kick Steve spam"]


async def test_ban_global_offline_no_expulsa_nada() -> None:
    """Jugador sin sesión abierta → no intenta kick (lo cubre PLAYER.JOINED)."""
    console = ScriptedConsole([("Kicked Steve from the game",)])
    harness = Harness(console)

    await harness.facade.ban_globally(
        BanPlayerGloballyCommand(
            gamertag="Steve",
            xuid=XUID,
            reason="spam",
            actor_id="admin-1",
        )
    )

    assert console.sent == []
