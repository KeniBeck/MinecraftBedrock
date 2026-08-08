"""Tests del ``BanEnforcementHandler`` (enforcement de bans en PLAYER.JOINED).

Cubre el matching por ``xuid`` con fallback a ``gamertag`` (case-insensitive,
``xuid=0`` offline, ban expirado) y el kick con el motivo correcto para bans
globales y por servidor (ADR-011).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerState
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.streaming import ConsoleOutputRouter
from app.modules.console.application.use_cases import ConsoleDeps
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.player.application import use_cases as player_use_cases
from app.modules.player.application.facade import PlayerFacade
from app.modules.player.application.use_cases import PlayerDeps
from app.modules.player.domain.bans import GlobalBan, ServerBan
from app.modules.player.domain.events import PLAYER_JOINED
from app.modules.player.infrastructure.memory import (
    InMemoryPlayerBanRepository,
    InMemoryPlayerRepository,
)
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader, FakeSettings, FakeTime, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
XUID = "2535467050498296"


@pytest.fixture(autouse=True)
def _kick_retry_rapido(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ventana de observación y backoff mínimos para no ralentizar los tests."""
    monkeypatch.setattr(player_use_cases, "KICK_RETRY_BACKOFF_SECONDS", (0.001,) * 5)
    monkeypatch.setattr(player_use_cases, "KICK_OBSERVE_WINDOW_SECONDS", 0.001)


class Harness:
    """Facade de Player con consola real (escribe a ``FakeRuntime.stdin_writes``)."""

    def __init__(self) -> None:
        self.bus = InProcessEventBus()
        self.time = FakeTime(NOW)
        self.runtime = FakeRuntime()
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
            server=FakeServerReader(views={"srv-1": view, "srv-2": view}),
            runtime=self.runtime,
            bus=self.bus,
            time=self.time,
            settings=FakeSettings(),
            ids=SequenceIds("sub-1"),
            store=InMemoryConsoleLogStore(),
        )
        console = ConsoleFacade(
            deps=console_deps,
            queue=CommandQueue(runtime=self.runtime, bus=self.bus, time=self.time),
            router=ConsoleOutputRouter(store=console_deps.store, bus=self.bus),
        )
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
        facade = PlayerFacade(deps)
        facade.register_handlers()
        self.facade = facade

    async def join(self, server_id: str, name: str, xuid: str) -> None:
        await self.bus.publish(
            DomainEvent(
                type=PLAYER_JOINED,
                server_id=server_id,
                payload={"server_id": server_id, "name": name, "xuid": xuid},
            )
        )
        await self.facade.await_ban_enforcement()

    def kicks(self) -> list[str]:
        return [data for _, data in self.runtime.stdin_writes]


async def test_sin_ban_no_hay_kick() -> None:
    harness = Harness()
    await harness.join("srv-1", "Steve", XUID)
    assert harness.kicks() == []


async def test_ban_global_por_xuid_kick_con_reason() -> None:
    harness = Harness()
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

    assert harness.kicks() == ["kick Steve spam\n"]


async def test_ban_global_fallback_gamertag_con_xuid_0() -> None:
    """Offline: XUID ``0`` no es fiable → match por gamertag."""
    harness = Harness()
    await harness.ban_repo.save_global_ban(
        GlobalBan(
            id="gb-1",
            gamertag="Steve",
            reason="spam",
            banned_by="admin-1",
            created_at=NOW,
        )
    )

    await harness.join("srv-1", "Steve", "0")

    assert harness.kicks() == ["kick Steve spam\n"]


async def test_ban_global_case_insensitive() -> None:
    """El fallback por gamertag ignora mayúsculas/minúsculas."""
    harness = Harness()
    await harness.ban_repo.save_global_ban(
        GlobalBan(
            id="gb-1",
            gamertag="Steve",
            banned_by="admin-1",
            created_at=NOW,
        )
    )

    await harness.join("srv-1", "STEVE", "0")

    assert harness.kicks() == ["kick STEVE\n"]


async def test_ban_expirado_no_aplica() -> None:
    harness = Harness()
    await harness.ban_repo.save_global_ban(
        GlobalBan(
            id="gb-1",
            xuid=XUID,
            gamertag="Steve",
            reason="spam",
            banned_by="admin-1",
            created_at=NOW,
            expires_at=NOW - timedelta(minutes=1),
        )
    )

    await harness.join("srv-1", "Steve", XUID)

    assert harness.kicks() == []


async def test_ban_por_servidor_kick() -> None:
    harness = Harness()
    await harness.ban_repo.save_server_ban(
        ServerBan(
            id="sb-1",
            server_id="srv-1",
            xuid=XUID,
            gamertag="Steve",
            reason="cheats",
            banned_by="admin-1",
            created_at=NOW,
        )
    )

    await harness.join("srv-1", "Steve", XUID)

    assert harness.kicks() == ["kick Steve cheats\n"]


async def test_ban_por_servidor_no_aplica_en_otro_server() -> None:
    harness = Harness()
    await harness.ban_repo.save_server_ban(
        ServerBan(
            id="sb-1",
            server_id="srv-2",
            xuid=XUID,
            gamertag="Steve",
            banned_by="admin-1",
            created_at=NOW,
        )
    )

    await harness.join("srv-1", "Steve", XUID)

    assert harness.kicks() == []


async def test_ban_global_gana_sobre_servidor_sin_reason() -> None:
    """El ban global (con reason) se aplica antes que el ban por servidor."""
    harness = Harness()
    await harness.ban_repo.save_global_ban(
        GlobalBan(
            id="gb-1",
            gamertag="Steve",
            reason="spam",
            banned_by="admin-1",
            created_at=NOW,
        )
    )
    await harness.ban_repo.save_server_ban(
        ServerBan(
            id="sb-1",
            server_id="srv-1",
            gamertag="Steve",
            reason="cheats",
            banned_by="admin-1",
            created_at=NOW,
        )
    )

    await harness.join("srv-1", "Steve", "0")

    assert harness.kicks() == ["kick Steve spam\n"]
