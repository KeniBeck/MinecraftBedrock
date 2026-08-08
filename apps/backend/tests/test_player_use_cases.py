"""Tests de los use cases del módulo Player (Fase E paso 11).

Cubre caché de identidad, sesiones join/leave, playtime, limpieza de presencia
en ``SERVER.STARTED``, kick vía la facade Console y los bans persistentes
(globales y por servidor, ADR-011) con sus eventos. Se usa una ``ConsoleFacade``
real con dobles inyectados (mismo criterio que los tests de Console).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerState
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.results import CommandAck, ConsoleObservation
from app.modules.console.application.streaming import ConsoleOutputRouter
from app.modules.console.application.use_cases import ConsoleDeps
from app.modules.console.domain.command import CommandPriority
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.player.application import use_cases as player_use_cases
from app.modules.player.application.commands import (
    BanPlayerGloballyCommand,
    BanPlayerOnServerCommand,
    KickPlayerCommand,
    UnbanPlayerGloballyCommand,
    UnbanPlayerOnServerCommand,
)
from app.modules.player.application.use_cases import (
    BanPlayerGloballyUseCase,
    BanPlayerOnServerUseCase,
    CleanPresenceUseCase,
    JoinPlayerUseCase,
    KickPlayerUseCase,
    LeavePlayerUseCase,
    PlayerDeps,
    ResolvePlayerUseCase,
    UnbanPlayerGloballyUseCase,
    UnbanPlayerOnServerUseCase,
    kick_with_retry,
)
from app.modules.player.domain.errors import (
    PlayerBanNotFoundError,
    PlayerNotFoundError,
    PlayerValidationError,
)
from app.modules.player.domain.events import (
    PLAYER_BANNED,
    PLAYER_BANNED_TOPIC,
    PLAYER_UNBANNED,
    PLAYER_UNBANNED_TOPIC,
)
from app.modules.player.domain.session import SessionEndReason
from app.modules.player.infrastructure.memory import (
    InMemoryPlayerBanRepository,
    InMemoryPlayerRepository,
)
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader, FakeSettings, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
XUID = "2535467050498296"
NAME = "Steve"


@pytest.fixture(autouse=True)
def _kick_retry_rapido(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ventana de observación y backoff mínimos para no ralentizar los tests."""
    monkeypatch.setattr(player_use_cases, "KICK_RETRY_BACKOFF_SECONDS", (0.001,) * 5)
    monkeypatch.setattr(player_use_cases, "KICK_OBSERVE_WINDOW_SECONDS", 0.001)


class Clock:
    """``TimeProviderPort`` mutable para avanzar el reloj entre join/leave."""

    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int) -> None:
        self._now += timedelta(seconds=seconds)


def make_console(bus: InProcessEventBus, clock: Clock, runtime: FakeRuntime) -> ConsoleFacade:
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
        runtime=runtime,
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
        self.runtime = FakeRuntime()
        self.repository = InMemoryPlayerRepository()
        self.deps = PlayerDeps(
            repository=self.repository,
            ban_repository=InMemoryPlayerBanRepository(),
            console=make_console(self.bus, self.clock, self.runtime),
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


# -- bans globales / por servidor (persistidos, ADR-011) ---------------------


async def test_ban_global_persiste_y_publica_player_banned(fx: Fixture) -> None:
    banned: list[DomainEvent] = []
    fx.bus.subscribe(PLAYER_BANNED_TOPIC, banned.append)

    view = await BanPlayerGloballyUseCase(fx.deps).ban(
        BanPlayerGloballyCommand(
            gamertag="   Steve  ", xuid=XUID, reason="spam", actor_id="admin-1"
        )
    )

    assert view.gamertag == "Steve"
    assert view.scope == "global"
    assert view.xuid == XUID
    stored = await fx.deps.ban_repository.get_global_ban(view.id)
    assert stored is not None and stored.gamertag == "Steve"
    assert len(banned) == 1
    assert banned[0].type == PLAYER_BANNED
    assert banned[0].payload == {
        "scope": "global",
        "server_id": None,
        "xuid": XUID,
        "gamertag": "Steve",
        "reason": "spam",
    }
    assert banned[0].actor_id == "admin-1"


async def test_ban_global_sin_gamertag_rechazado(fx: Fixture) -> None:
    with pytest.raises(PlayerValidationError, match="gamertag requerido"):
        await BanPlayerGloballyUseCase(fx.deps).ban(BanPlayerGloballyCommand(gamertag=" "))


async def test_ban_global_actualiza_existente_por_gamertag(fx: Fixture) -> None:
    first = await BanPlayerGloballyUseCase(fx.deps).ban(
        BanPlayerGloballyCommand(gamertag="Steve", xuid=XUID, reason="spam")
    )

    second = await BanPlayerGloballyUseCase(fx.deps).ban(
        BanPlayerGloballyCommand(gamertag="steve", reason="otra razón")
    )

    assert second.id == first.id  # misma fila (unicidad por gamertag lower-case)


async def test_unban_global_elimina_y_publica_player_unbanned(fx: Fixture) -> None:
    view = await BanPlayerGloballyUseCase(fx.deps).ban(
        BanPlayerGloballyCommand(gamertag="Steve", xuid=XUID, reason="spam")
    )
    unbanned: list[DomainEvent] = []
    fx.bus.subscribe(PLAYER_UNBANNED_TOPIC, unbanned.append)

    await UnbanPlayerGloballyUseCase(fx.deps).unban(
        UnbanPlayerGloballyCommand(ban_id=view.id, actor_id="admin-1")
    )

    assert await fx.deps.ban_repository.get_global_ban(view.id) is None
    assert len(unbanned) == 1
    assert unbanned[0].type == PLAYER_UNBANNED
    assert unbanned[0].payload["scope"] == "global"
    assert unbanned[0].payload["ban_id"] == view.id
    assert unbanned[0].actor_id == "admin-1"


async def test_unban_global_no_encontrado(fx: Fixture) -> None:
    with pytest.raises(PlayerBanNotFoundError):
        await UnbanPlayerGloballyUseCase(fx.deps).unban(
            UnbanPlayerGloballyCommand(ban_id="no-existe")
        )


async def test_ban_por_servidor_persiste_y_expulsa_si_online(fx: Fixture) -> None:
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)
    await JoinPlayerUseCase(fx.deps).join("srv-1", XUID, NAME)
    banned: list[DomainEvent] = []
    fx.bus.subscribe(PLAYER_BANNED_TOPIC, banned.append)

    view = await BanPlayerOnServerUseCase(fx.deps).ban(
        BanPlayerOnServerCommand(
            server_id="srv-1",
            player_id=XUID,
            reason="cheats",
            actor_id="admin-1",
        )
    )

    assert view.scope == "server"
    assert view.server_id == "srv-1"
    stored = await fx.deps.ban_repository.get_server_ban("srv-1", view.id)
    assert stored is not None and stored.gamertag == NAME
    assert banned[0].type == PLAYER_BANNED
    assert banned[0].payload["scope"] == "server"
    assert banned[0].payload["server_id"] == "srv-1"
    assert banned[0].payload["gamertag"] == NAME
    kicks = [data for _, data in fx.runtime.stdin_writes]
    assert kicks == ["kick Steve cheats\n"]


async def test_ban_por_servidor_sin_reason_usa_el_motivo_por_defecto(fx: Fixture) -> None:
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)
    await JoinPlayerUseCase(fx.deps).join("srv-1", XUID, NAME)

    await BanPlayerOnServerUseCase(fx.deps).ban(
        BanPlayerOnServerCommand(server_id="srv-1", player_id=XUID, actor_id="admin-1")
    )

    kicks = [data for _, data in fx.runtime.stdin_writes]
    assert kicks == ["kick Steve Baneado del servidor\n"]


async def test_ban_por_servidor_no_expulsa_si_no_esta_online(fx: Fixture) -> None:
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)

    view = await BanPlayerOnServerUseCase(fx.deps).ban(
        BanPlayerOnServerCommand(server_id="srv-1", player_id=XUID, reason="cheats")
    )

    stored = await fx.deps.ban_repository.get_server_ban("srv-1", view.id)
    assert stored is not None
    assert fx.runtime.stdin_writes == []


async def test_ban_por_servidor_de_jugador_desconocido(fx: Fixture) -> None:
    with pytest.raises(PlayerNotFoundError):
        await BanPlayerOnServerUseCase(fx.deps).ban(
            BanPlayerOnServerCommand(server_id="srv-1", player_id="9999999999999999")
        )


async def test_unban_por_servidor_elimina_y_publica(fx: Fixture) -> None:
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)
    view = await BanPlayerOnServerUseCase(fx.deps).ban(
        BanPlayerOnServerCommand(server_id="srv-1", player_id=XUID, reason="cheats")
    )
    unbanned: list[DomainEvent] = []
    fx.bus.subscribe(PLAYER_UNBANNED_TOPIC, unbanned.append)

    await UnbanPlayerOnServerUseCase(fx.deps).unban(
        UnbanPlayerOnServerCommand(server_id="srv-1", player_id=XUID, actor_id="admin-1")
    )

    assert await fx.deps.ban_repository.get_server_ban("srv-1", view.id) is None
    assert len(unbanned) == 1
    assert unbanned[0].type == PLAYER_UNBANNED
    assert unbanned[0].payload["scope"] == "server"
    assert unbanned[0].payload["server_id"] == "srv-1"
    assert unbanned[0].payload["ban_id"] == view.id


async def test_unban_por_servidor_sin_ban_no_encontrado(fx: Fixture) -> None:
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)
    with pytest.raises(PlayerBanNotFoundError):
        await UnbanPlayerOnServerUseCase(fx.deps).unban(
            UnbanPlayerOnServerCommand(server_id="srv-1", player_id=XUID)
        )


async def test_kick_envia_comando_por_nombre(fx: Fixture) -> None:
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)

    ack = await KickPlayerUseCase(fx.deps).kick(KickPlayerCommand(server_id="srv-1", xuid=XUID))

    assert ack.command == f"kick {NAME}"


async def test_kick_rechaza_xuid_vacio(fx: Fixture) -> None:
    with pytest.raises(PlayerValidationError):
        await KickPlayerUseCase(fx.deps).kick(KickPlayerCommand(server_id="srv-1", xuid=""))


async def test_kick_with_retry_tope_de_intentos(
    fx: Fixture, caplog: pytest.LogCaptureFixture
) -> None:
    """Todos los intentos fallan → se agotan los ``KICK_MAX_ATTEMPTS`` y se loguea el fallo."""
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)
    await JoinPlayerUseCase(fx.deps).join("srv-1", XUID, NAME)
    fallos = [
        ConsoleObservation(
            ack=CommandAck(
                server_id="srv-1",
                command=f"kick {NAME} spam",
                priority=CommandPriority.NORMAL,
                seq=i,
                at=NOW,
            ),
            lines=("No targets matched selector",),
        )
        for i in range(1, 4)
    ]

    class _ConsolaFallona(ConsoleFacade):
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send_command_and_observe(
            self, cmd: SendCommand, *, window_s: float
        ) -> ConsoleObservation:
            del window_s
            self.sent.append(cmd.command)
            return fallos[len(self.sent) - 1]

    consola = _ConsolaFallona()
    deps = PlayerDeps(
        repository=fx.repository,
        ban_repository=fx.deps.ban_repository,
        console=consola,
        bus=fx.bus,
        ids=fx.deps.ids,
        time=fx.clock,
        settings=fx.deps.settings,
    )
    with caplog.at_level(logging.WARNING, logger="app.modules.player.application.use_cases"):
        await kick_with_retry(deps, "srv-1", XUID, NAME, "spam", None)

    assert consola.sent == [f"kick {NAME} spam"] * 3
    assert "player.ban_kick_failed" in caplog.text


async def test_kick_with_retry_corta_si_el_jugador_se_desconecta(fx: Fixture) -> None:
    """Tras el primer fallo el jugador deja de estar online → el retry se corta."""
    await ResolvePlayerUseCase(fx.deps).cache(XUID, NAME)
    await JoinPlayerUseCase(fx.deps).join("srv-1", XUID, NAME)

    class _ConsolaConDesconexion(ConsoleFacade):
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send_command_and_observe(
            self, cmd: SendCommand, *, window_s: float
        ) -> ConsoleObservation:
            del window_s
            self.sent.append(cmd.command)
            if len(self.sent) == 1:
                await LeavePlayerUseCase(fx.deps).leave("srv-1", XUID, NAME)
            return ConsoleObservation(
                ack=CommandAck(
                    server_id="srv-1",
                    command=cmd.command,
                    priority=cmd.priority,
                    seq=len(self.sent),
                    at=NOW,
                ),
                lines=("No targets matched selector",),
            )

    consola = _ConsolaConDesconexion()
    deps = PlayerDeps(
        repository=fx.repository,
        ban_repository=fx.deps.ban_repository,
        console=consola,
        bus=fx.bus,
        ids=fx.deps.ids,
        time=fx.clock,
        settings=fx.deps.settings,
    )
    await kick_with_retry(deps, "srv-1", XUID, NAME, "spam", None)

    assert consola.sent == [f"kick {NAME} spam"]
