"""Tests de los handlers de eventos del módulo Player (Fase E paso 11).

Verifica el contrato de consumo: ``PLAYER.JOINED``/``PLAYER.LEFT`` (publicados
por los parsers de Console) abren/cierran sesiones, ``SERVER.STARTED`` limpia
la presencia y ``PLAYER.OPERATOR_CHANGED`` se consume solo por consistencia.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerState
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.streaming import ConsoleOutputRouter
from app.modules.console.application.use_cases import ConsoleDeps
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.player.application.facade import PlayerFacade
from app.modules.player.application.handlers import SERVER_STARTED_TOPIC
from app.modules.player.application.use_cases import PlayerDeps
from app.modules.player.domain.events import (
    PLAYER_JOINED,
    PLAYER_JOINED_TOPIC,
    PLAYER_LEFT,
    PLAYER_LEFT_TOPIC,
    PLAYER_OPERATOR_CHANGED,
    PLAYER_OPERATOR_CHANGED_TOPIC,
)
from app.modules.player.infrastructure.memory import InMemoryPlayerRepository
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader, FakeSettings, FakeTime, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
XUID = "2535467050498296"


def make_facade() -> PlayerFacade:
    bus = InProcessEventBus()
    time = FakeTime(NOW)
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
        runtime=FakeRuntime(),
        bus=bus,
        time=time,
        settings=FakeSettings(),
        ids=SequenceIds("sub-1"),
        store=InMemoryConsoleLogStore(),
    )
    console = ConsoleFacade(
        deps=console_deps,
        queue=CommandQueue(runtime=console_deps.runtime, bus=bus, time=time),
        router=ConsoleOutputRouter(store=console_deps.store, bus=bus),
    )
    deps = PlayerDeps(
        repository=InMemoryPlayerRepository(),
        console=console,
        bus=bus,
        ids=SequenceIds("s-1", "s-2"),
        time=time,
        settings=FakeSettings(),
    )
    facade = PlayerFacade(deps)
    facade.register_handlers()
    return facade


def join_event() -> DomainEvent:
    return DomainEvent(
        type=PLAYER_JOINED,
        server_id="srv-1",
        payload={"server_id": "srv-1", "name": "Steve", "xuid": XUID},
    )


def left_event() -> DomainEvent:
    return DomainEvent(
        type=PLAYER_LEFT,
        server_id="srv-1",
        payload={"server_id": "srv-1", "name": "Steve", "xuid": XUID},
    )


async def test_player_joined_abre_sesion() -> None:
    facade = make_facade()

    await facade.deps.bus.publish(join_event())

    player = await facade.deps.repository.get_player(XUID)
    assert player is not None
    session = await facade.deps.repository.get_open_session("srv-1", XUID)
    assert session is not None
    assert session.left_at is None


async def test_player_left_cierra_sesion() -> None:
    facade = make_facade()
    await facade.deps.bus.publish(join_event())

    await facade.deps.bus.publish(left_event())

    session = await facade.deps.repository.get_open_session("srv-1", XUID)
    assert session is None


async def test_joined_sin_payload_valido_se_ignora() -> None:
    facade = make_facade()

    await facade.deps.bus.publish(DomainEvent(type=PLAYER_JOINED, server_id="srv-1", payload={}))

    assert await facade.deps.repository.get_player(XUID) is None


async def test_joined_sin_server_id_se_ignora() -> None:
    facade = make_facade()
    event = join_event()
    event_payload = dict(event.payload)
    event_payload.pop("server_id")
    await facade.deps.bus.publish(DomainEvent(type=PLAYER_JOINED, payload=event_payload))

    assert await facade.deps.repository.get_player(XUID) is None


async def test_server_started_limpia_presencia() -> None:
    facade = make_facade()
    await facade.deps.bus.publish(join_event())

    await facade.deps.bus.publish(
        DomainEvent(type="SERVER.STARTED", server_id="srv-1", payload={"server_id": "srv-1"})
    )

    assert await facade.deps.repository.get_open_session("srv-1", XUID) is None


async def test_operator_changed_se_consume_sin_efecto() -> None:
    facade = make_facade()

    await facade.deps.bus.publish(
        DomainEvent(
            type=PLAYER_OPERATOR_CHANGED,
            server_id="srv-1",
            payload={"server_id": "srv-1", "xuid": XUID, "operator": True},
        )
    )

    assert await facade.deps.repository.get_player(XUID) is None


async def test_topics_suscritos() -> None:
    facade = make_facade()
    topics = cast(InProcessEventBus, facade.deps.bus)._subscribers

    assert PLAYER_JOINED_TOPIC in topics
    assert PLAYER_LEFT_TOPIC in topics
    assert SERVER_STARTED_TOPIC in topics
    assert PLAYER_OPERATOR_CHANGED_TOPIC in topics
