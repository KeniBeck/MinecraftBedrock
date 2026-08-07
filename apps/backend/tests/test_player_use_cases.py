"""Tests de los use cases del módulo Player (Fase E paso 11).

Cubre caché de identidad, sesiones join/leave, playtime, limpieza de presencia
en ``SERVER.STARTED`` y ban/unban/kick vía la facade Console. Se usa una
``ConsoleFacade`` real con dobles inyectados (mismo criterio que los tests de
Console).
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
from app.modules.player.application.commands import (
    BanPlayerCommand,
    KickPlayerCommand,
    UnbanPlayerCommand,
)
from app.modules.player.application.use_cases import (
    BanPlayerUseCase,
    CleanPresenceUseCase,
    JoinPlayerUseCase,
    KickPlayerUseCase,
    LeavePlayerUseCase,
    PlayerDeps,
    ResolvePlayerUseCase,
    UnbanPlayerUseCase,
)
from app.modules.player.domain.errors import PlayerNotFoundError, PlayerValidationError
from app.modules.player.domain.events import (
    PLAYER_BANNED,
    PLAYER_BANNED_TOPIC,
)
from app.modules.player.domain.session import SessionEndReason
from app.modules.player.infrastructure.memory import InMemoryPlayerRepository
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader, FakeSettings, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
XUID = "2535467050498296"
NAME = "Steve"


class Clock:
    """``TimeProviderPort`` mutable para avanzar el reloj entre join/leave."""

    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int) -> None:
        self._now += timedelta(seconds=seconds)


def make_console(bus: InProcessEventBus, clock: Clock) -> ConsoleFacade:
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
    deps = ConsoleDeps(
        server=FakeServerReader(views={"srv-1": view}),
        runtime=FakeRuntime(),
        bus=bus,
        time=clock,
        settings=FakeSettings(),
        ids=SequenceIds("sub-1"),
        store=InMemoryConsoleLogStore(),
    )
    queue = CommandQueue(runtime=deps.runtime, bus=bus, time=clock)
    router = ConsoleOutputRouter(store=deps.store, bus=bus)
    return ConsoleFacade(deps=deps, queue=queue, router=router)


class Fixture:
    """Deps del módulo Player con dobles + un reloj mutable."""

    def __init__(self) -> None:
        self.bus = InProcessEventBus()
        self.clock = Clock()
        self.repository = InMemoryPlayerRepository()
        self.deps = PlayerDeps(
            repository=self.repository,
            console=make_console(self.bus, self.clock),
            bus=self.bus,
            ids=SequenceIds("s-1", "s-2", "s-3"),
            time=self.clock,
            settings=FakeSettings(),
        )


@pytest.fixture
def fx() -> Fixture:
    return Fixture()


# -- caché de identidad --------------------------------------------------------


async def test_resolve_cachea_un_jugador_nuevo(fx: Fixture) -> None:
    view = await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)

    assert view.xuid == XUID
    assert view.name == NAME
    assert view.playtime_seconds == 0

    player = await fx.repository.get_player(XUID)
    assert player is not None
    assert player.first_seen_at == NOW
    assert player.last_seen_at == NOW


async def test_resolve_refresca_nombre_y_ultima_visita(fx: Fixture) -> None:
    resolve = ResolvePlayerUseCase(fx.deps)
    await resolve.cache(XUID, NAME)
    fx.clock.advance(60)

    view = await resolve.cache(XUID, "Steve Renombrado")

    assert view.name == "Steve Renombrado"
    player = await fx.repository.get_player(XUID)
    assert player is not None
    assert player.last_seen_at > player.first_seen_at


async def test_resolve_rechaza_identidad_vacia(fx: Fixture) -> None:
    with pytest.raises(PlayerValidationError):
        await ResolvePlayerUseCase(fx.deps).cache("", NAME)


# -- sesiones ------------------------------------------------------------------


async def test_join_abre_sesion(fx: Fixture) -> None:
    view = await JoinPlayerUseCase(fx.deps).join("srv-1", XUID, NAME)

    assert view.server_id == "srv-1"
    assert view.xuid == XUID
    assert view.left_at is None
    assert view.reason is None

    player = await fx.repository.get_player(XUID)
    assert player is not None


async def test_join_es_idempotente_si_ya_hay_sesion_abierta(fx: Fixture) -> None:
    join = JoinPlayerUseCase(fx.deps)
    first = await join.join("srv-1", XUID, NAME)
    second = await join.join("srv-1", XUID, NAME)

    assert second.id == first.id


async def test_leave_cierra_sesion_y_acumula_playtime(fx: Fixture) -> None:
    join = JoinPlayerUseCase(fx.deps)
    await join.join("srv-1", XUID, NAME)
    fx.clock.advance(90)

    closed = await LeavePlayerUseCase(fx.deps).leave("srv-1", XUID, NAME)

    assert closed is not None
    assert closed.left_at == NOW + timedelta(seconds=90)
    assert closed.reason == SessionEndReason.LEFT.value
    assert closed.playtime_seconds == 90

    player = await fx.repository.get_player(XUID)
    assert player is not None
    assert player.playtime_seconds == 90


async def test_leave_acumula_entre_varias_sesiones(fx: Fixture) -> None:
    join = JoinPlayerUseCase(fx.deps)
    leave = LeavePlayerUseCase(fx.deps)
    await join.join("srv-1", XUID, NAME)
    fx.clock.advance(120)
    await leave.leave("srv-1", XUID, NAME)
    await join.join("srv-1", XUID, NAME)
    fx.clock.advance(30)
    await leave.leave("srv-1", XUID, NAME)

    player = await fx.repository.get_player(XUID)
    assert player is not None
    assert player.playtime_seconds == 150


async def test_leave_sin_sesion_abierta_es_defensivo(fx: Fixture) -> None:
    result = await LeavePlayerUseCase(fx.deps).leave("srv-1", XUID, NAME)

    assert result is None
    player = await fx.repository.get_player(XUID)
    assert player is not None  # la caché se refresca igualmente


# -- limpieza de presencia (SERVER.STARTED) ------------------------------------


async def test_clean_aborta_sesiones_sin_acumular_playtime(fx: Fixture) -> None:
    join = JoinPlayerUseCase(fx.deps)
    await join.join("srv-1", XUID, NAME)
    await join.join("srv-1", "2535467050498297", "Alex")
    fx.clock.advance(300)

    closed = await CleanPresenceUseCase(fx.deps).clean("srv-1")

    assert closed == 2
    player = await fx.repository.get_player(XUID)
    assert player is not None
    assert player.playtime_seconds == 0  # sesión abortada: sin playtime
    sessions = await fx.repository.list_open_sessions("srv-1")
    assert sessions == []


async def test_clean_no_afecta_a_otros_servidores(fx: Fixture) -> None:
    join = JoinPlayerUseCase(fx.deps)
    await join.join("srv-1", XUID, NAME)
    await join.join("srv-2", XUID, NAME)

    await CleanPresenceUseCase(fx.deps).clean("srv-1")

    remaining = await fx.repository.get_open_session("srv-2", XUID)
    assert remaining is not None


# -- bans / unban / kick (vía facade Console) ----------------------------------


async def test_ban_envia_comando_y_publica_player_banned(fx: Fixture) -> None:
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)
    banned: list[DomainEvent] = []
    fx.bus.subscribe(PLAYER_BANNED_TOPIC, banned.append)

    ack = await BanPlayerUseCase(fx.deps).ban(
        BanPlayerCommand(server_id="srv-1", xuid=XUID, actor_id="admin-1")
    )

    assert ack.command == f"ban {NAME}"
    assert len(banned) == 1
    assert banned[0].type == PLAYER_BANNED
    assert banned[0].payload == {
        "server_id": "srv-1",
        "xuid": XUID,
        "name": NAME,
        "command": f"ban {NAME}",
    }
    assert banned[0].actor_id == "admin-1"


async def test_ban_de_jugador_desconocido_levanta_not_found(fx: Fixture) -> None:
    with pytest.raises(PlayerNotFoundError):
        await BanPlayerUseCase(fx.deps).ban(
            BanPlayerCommand(server_id="srv-1", xuid="9999999999999999")
        )


async def test_unban_envia_comando_por_xuid(fx: Fixture) -> None:
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)

    ack = await UnbanPlayerUseCase(fx.deps).unban(UnbanPlayerCommand(server_id="srv-1", xuid=XUID))

    assert ack.command == f"unban {XUID}"


async def test_kick_envia_comando_por_nombre(fx: Fixture) -> None:
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)

    ack = await KickPlayerUseCase(fx.deps).kick(KickPlayerCommand(server_id="srv-1", xuid=XUID))

    assert ack.command == f"kick {NAME}"


async def test_unban_rechaza_xuid_vacio(fx: Fixture) -> None:
    with pytest.raises(PlayerValidationError):
        await UnbanPlayerUseCase(fx.deps).unban(UnbanPlayerCommand(server_id="srv-1", xuid=""))
