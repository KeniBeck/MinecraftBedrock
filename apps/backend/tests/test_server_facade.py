"""Tests end-to-end de la facade pública del módulo Server (Blueprint §3.2)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerState
from app.modules.server.application.commands import (
    ApplyConfigCommand,
    ChangeVersionCommand,
    CreateServerCommand,
    RemoveServerCommand,
    RestartServerCommand,
    StartServerCommand,
    StopServerCommand,
)
from app.modules.server.application.facade import ServerFacade
from app.modules.server.application.spec_factory import RuntimeSpecFactory
from app.modules.server.application.use_cases import ServerDeps
from app.modules.server.domain.server import ServerId
from app.modules.server.infrastructure.repository import InMemoryServerRepository
from tests.conftest import (
    FakeConfigurationReader,
    FakeRuntime,
    FakeSettings,
    FakeTime,
    SequenceIds,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_facade(
    config: FakeConfigurationReader | None = None,
    runtime: FakeRuntime | None = None,
    bus: InProcessEventBus | None = None,
) -> tuple[ServerFacade, FakeRuntime, FakeConfigurationReader, InProcessEventBus]:
    bus = bus or InProcessEventBus()
    runtime = runtime or FakeRuntime()
    config = config or FakeConfigurationReader()
    settings = FakeSettings()
    spec_factory = RuntimeSpecFactory(settings)
    repository = InMemoryServerRepository()
    deps = ServerDeps(
        repository=repository,
        runtime=runtime,
        bus=bus,
        ids=SequenceIds("srv-1"),
        time=FakeTime(NOW),
        settings=settings,
        configuration=config,
        spec_factory=spec_factory,
    )
    facade = ServerFacade(
        repository=repository,
        configuration=config,
        spec_factory=spec_factory,
        deps=deps,
    )
    facade.register_handlers()
    return facade, runtime, config, bus


async def test_ciclo_vida_completo_via_facade() -> None:
    facade, runtime, _, _ = make_facade()

    created = await facade.create(CreateServerCommand(name="Survival"))
    assert created.state == ServerState.CREATED

    started = await facade.start(StartServerCommand(server_id=created.id))
    assert started.state == ServerState.STARTING

    running = await facade.mark_started(created.id)
    assert running.state == ServerState.RUNNING

    stopped = await facade.stop(StopServerCommand(server_id=created.id))
    assert stopped.state == ServerState.STOPPED

    restarted = await facade.restart(RestartServerCommand(server_id=created.id))
    assert restarted.state == ServerState.STARTING

    crashed = await facade.mark_crashed(created.id)
    assert crashed.state == ServerState.CRASHED

    await facade.remove(RemoveServerCommand(server_id=created.id))
    view = await facade.get_server(created.id)
    assert view is not None and view.state == ServerState.REMOVED
    assert runtime.removed != []


async def test_evento_config_changed_dispara_apply_config() -> None:
    facade, runtime, config, bus = make_facade()
    created = await facade.create(CreateServerCommand(name="Survival"))
    old_runtime = runtime.materialized[0]

    config.env["MOTD"] = "cambiado"
    await bus.publish(
        DomainEvent(type="CONFIG.CHANGED", server_id=created.id, payload={"config_rev": 7})
    )

    view = await facade.get_server(created.id)
    assert view is not None
    assert view.id == created.id
    assert len(runtime.materialized) == 2  # se recreó
    assert runtime.removed[0][0] == old_runtime
    new_spec = runtime.specs[runtime.materialized[-1]]
    assert new_spec.environment["MOTD"] == "cambiado"


async def test_change_version_via_facade() -> None:
    facade, runtime, _, _ = make_facade()
    created = await facade.create(CreateServerCommand(name="Survival"))

    view = await facade.change_version(ChangeVersionCommand(server_id=created.id, version="1.21.0"))

    assert view.version == "1.21.0"
    server = await facade.repository.get(ServerId(created.id))
    assert server is not None
    assert server.spec.version == "1.21.0"
    assert len(runtime.materialized) == 2


async def test_consultas_list_y_get() -> None:
    facade, _, _, _ = make_facade()
    assert await facade.list_servers() == []
    await facade.create(CreateServerCommand(name="Survival"))
    servers = await facade.list_servers()
    assert len(servers) == 1
    assert servers[0].name == "Survival"


async def test_apply_config_directo_via_facade() -> None:
    facade, _, config, _ = make_facade()
    created = await facade.create(CreateServerCommand(name="Survival"))
    config.env["MOTD"] = "directo"
    view = await facade.apply_config(ApplyConfigCommand(server_id=created.id, config_rev=2))
    assert view.state == ServerState.CREATED
    server = await facade.repository.get(ServerId(created.id))
    assert server is not None
    assert server.applied_config_rev == 2
