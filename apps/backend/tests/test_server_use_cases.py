"""Tests de los use cases del módulo Server (ciclo de vida, config, versión)."""

from __future__ import annotations

import pathlib
from datetime import UTC, datetime

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import RuntimeSpec, ServerState
from app.modules.server.application import spec_factory as spec_factory_module
from app.modules.server.application.commands import (
    ApplyConfigCommand,
    ChangeVersionCommand,
    CreateServerCommand,
    RemoveServerCommand,
    RestartServerCommand,
    StartServerCommand,
    StopServerCommand,
)
from app.modules.server.application.ports import ConfigurationReader, DesiredConfig
from app.modules.server.application.spec_factory import RuntimeSpecFactory
from app.modules.server.application.use_cases import (
    ApplyConfigUseCase,
    ChangeVersionUseCase,
    CreateServerUseCase,
    MarkCrashedUseCase,
    MarkStartedUseCase,
    OperationGuard,
    RemoveServerUseCase,
    RestartServerUseCase,
    ServerDeps,
    StartServerUseCase,
    StopServerUseCase,
)
from app.modules.server.domain.errors import (
    ServerNotFoundError,
    ServerNotMaterializedError,
    ServerStateError,
)
from app.modules.server.domain.events import (
    SERVER_CONFIG_CHANGED,
    SERVER_CRASHED,
    SERVER_CREATED,
    SERVER_REMOVED,
    SERVER_STARTED,
    SERVER_STARTING,
    SERVER_STOPPED,
    SERVER_STOPPING,
    SERVER_TOPIC_WILDCARD,
    SERVER_VERSION_CHANGED,
)
from app.modules.server.domain.server import Server, ServerId
from app.modules.server.infrastructure.repository import InMemoryServerRepository
from tests.conftest import (
    FakeConfigurationReader,
    FakeRuntime,
    FakeSettings,
    FakeTime,
    SequenceIds,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class Recorder:
    """Suscriptor al comodín ``server.*`` que graba eventos."""

    def __init__(self, bus: InProcessEventBus) -> None:
        self.types: list[str] = []
        self.events: list[DomainEvent] = []
        bus.subscribe(SERVER_TOPIC_WILDCARD, self._record)

    async def _record(self, event: DomainEvent) -> None:
        self.events.append(event)
        self.types.append(event.type)


def make_deps(
    runtime: FakeRuntime,
    configuration: ConfigurationReader,
    bus: InProcessEventBus,
    *,
    ids: SequenceIds | None = None,
    settings_values: dict[str, object] | None = None,
) -> ServerDeps:
    settings = FakeSettings(settings_values)
    spec_factory = RuntimeSpecFactory(settings)
    return ServerDeps(
        repository=InMemoryServerRepository(),
        runtime=runtime,
        bus=bus,
        ids=ids or SequenceIds("srv-1", "srv-2"),
        time=FakeTime(NOW),
        settings=settings,
        configuration=configuration,
        spec_factory=spec_factory,
    )


async def make_running(deps: ServerDeps, runtime: FakeRuntime) -> str:
    view = await CreateServerUseCase(deps).execute(CreateServerCommand(name="Survival"))
    await StartServerUseCase(deps).execute(StartServerCommand(server_id=view.id))
    await MarkStartedUseCase(deps).execute(view.id)
    return view.id


async def test_crear_servidor_publica_created_y_materializa() -> None:
    bus = InProcessEventBus()
    recorder = Recorder(bus)
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(), bus)

    view = await CreateServerUseCase(deps).execute(
        CreateServerCommand(name="Survival", actor_id="u1")
    )

    assert view.id == "srv-1"
    assert view.state == ServerState.CREATED
    assert runtime.materialized == ["r0"]
    assert view.runtime_id == "r0"
    assert SERVER_CREATED in recorder.types
    created = recorder.events[0]
    assert created.server_id == "srv-1"
    assert created.actor_id == "u1"


async def test_crear_servidor_honra_version_del_comando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(version="1.20.0"), bus)
    monkeypatch.setattr(
        spec_factory_module,
        "_local_bedrock_binary_exists",
        lambda *args, **kwargs: False,
    )

    view = await CreateServerUseCase(deps).execute(
        CreateServerCommand(name="Survival", version="1.21.1", actor_id="u1")
    )

    assert view.version == "1.21.1"
    assert runtime.specs["r0"].version == "1.21.1"
    assert runtime.specs["r0"].environment["VERSION"] == "1.21.1"


def test_spec_usa_version_existing_si_hay_binario_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        spec_factory_module,
        "_local_bedrock_binary_exists",
        lambda data_dir, version: True,
    )

    settings = FakeSettings({"storage.base_path": "/tmp/bedrockpanel"})
    spec_factory = RuntimeSpecFactory(settings)
    spec = spec_factory.render(
        "srv-1",
        "Survival",
        DesiredConfig(version="1.26.40.8", environment={}, config_rev=1),
    )

    assert spec.environment["VERSION"] == "EXISTING"
    assert spec.volumes[0].endswith(":/data")


def test_spec_detecta_binario_en_directorio_data_del_repo(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_data_dir = tmp_path / "data"
    repo_data_dir.mkdir()
    (repo_data_dir / "bedrock_server-1.26.40.8").write_text("bin", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    settings = FakeSettings({"storage.base_path": "/tmp/bedrockpanel"})
    spec_factory = RuntimeSpecFactory(settings)
    spec = spec_factory.render(
        "srv-1",
        "Survival",
        DesiredConfig(version="1.26.40.8", environment={}, config_rev=1),
    )

    assert spec.environment["VERSION"] == "EXISTING"
    assert spec.volumes[0].endswith(":/data")


def test_spec_usa_existing_cuando_hay_binario_local_con_otra_version(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_data_dir = tmp_path / "data"
    repo_data_dir.mkdir()
    (repo_data_dir / "bedrock_server-1.26.40.8").write_text("bin", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    settings = FakeSettings({"storage.base_path": "/tmp/bedrockpanel"})
    spec_factory = RuntimeSpecFactory(settings)
    spec = spec_factory.render(
        "srv-1",
        "Survival",
        DesiredConfig(version="1.26.33", environment={}, config_rev=1),
    )

    assert spec.environment["VERSION"] == "EXISTING"


async def test_spec_usa_config_deseada_env_y_b7() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    deps = make_deps(
        runtime,
        FakeConfigurationReader(env={"MOTD": "Hola", "LEVEL_NAME": "mundo"}),
        bus,
    )
    await CreateServerUseCase(deps).execute(CreateServerCommand(name="Survival"))
    spec = runtime.specs["r0"]
    assert spec.version == "1.20.0"
    assert spec.environment["MOTD"] == "Hola"
    assert spec.environment["LEVEL_NAME"] == "mundo"
    assert spec.environment["EULA"] == "TRUE"
    assert spec.environment["ONLINE_MODE"] == "false"
    assert spec.environment["ENABLE_LAN_VISIBILITY"] == "true"
    assert spec.ports == {"19132/udp": 19132, "19133/udp": 19133, "25575/tcp": 25575}
    assert spec.labels["bedrockpanel.server_id"] == "srv-1"


async def test_start_y_confirm_started() -> None:
    bus = InProcessEventBus()
    recorder = Recorder(bus)
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(), bus)
    server_id = "srv-1"
    await CreateServerUseCase(deps).execute(CreateServerCommand(name="Survival"))
    await StartServerUseCase(deps).execute(StartServerCommand(server_id=server_id))

    server = await deps.repository.get_required(ServerId(server_id))
    assert server.state == ServerState.STARTING
    assert SERVER_STARTING in recorder.types

    running = await MarkStartedUseCase(deps).execute(server_id)
    assert running.state == ServerState.RUNNING
    assert SERVER_STARTED in recorder.types


async def test_stop_ordenada_publica_stopping_y_stopped() -> None:
    bus = InProcessEventBus()
    recorder = Recorder(bus)
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(), bus)
    server_id = await make_running(deps, runtime)

    view = await StopServerUseCase(deps).execute(StopServerCommand(server_id=server_id, grace=5))

    assert view.state == ServerState.STOPPED
    assert runtime.stopped == [("r0", 5)]
    assert SERVER_STOPPING in recorder.types
    assert SERVER_STOPPED in recorder.types


async def test_mark_crashed() -> None:
    bus = InProcessEventBus()
    recorder = Recorder(bus)
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(), bus)
    server_id = await make_running(deps, runtime)

    view = await MarkCrashedUseCase(deps).execute(server_id)

    assert view.state == ServerState.CRASHED
    assert SERVER_CRASHED in recorder.types


async def test_restart_serializado() -> None:
    bus = InProcessEventBus()
    recorder = Recorder(bus)
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(), bus)
    guard = OperationGuard()
    server_id = await make_running(deps, runtime)

    view = await RestartServerUseCase(deps, guard).execute(
        RestartServerCommand(server_id=server_id)
    )

    assert view.state == ServerState.STARTING
    assert SERVER_STOPPED in recorder.types
    assert SERVER_STARTING in recorder.types


async def test_restart_desde_stopped_no_publica_stopped() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(), bus)
    guard = OperationGuard()
    server_id = await make_running(deps, runtime)
    await StopServerUseCase(deps).execute(StopServerCommand(server_id=server_id))

    recorder = Recorder(bus)
    view = await RestartServerUseCase(deps, guard).execute(
        RestartServerCommand(server_id=server_id)
    )

    assert view.state == ServerState.STARTING
    assert SERVER_STOPPED not in recorder.types
    assert SERVER_STARTING in recorder.types


async def test_remove_elimina_runtime_y_publica_removed() -> None:
    bus = InProcessEventBus()
    recorder = Recorder(bus)
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(), bus)
    guard = OperationGuard()
    server_id = await make_running(deps, runtime)

    await RemoveServerUseCase(deps, guard).execute(
        RemoveServerCommand(server_id=server_id, delete_data=True)
    )

    assert runtime.removed == [("r0", True)]
    assert runtime.stopped != []
    assert SERVER_REMOVED in recorder.types
    server = await deps.repository.get_required(ServerId(server_id))
    assert server.state == ServerState.REMOVED


async def test_guard_rechaza_operacion_en_curso() -> None:
    guard = OperationGuard()
    async with guard.locked("srv-1"):
        with pytest.raises(ServerStateError):
            async with guard.locked("srv-1"):
                pass


async def test_apply_config_recrea_si_cambia() -> None:
    bus = InProcessEventBus()
    recorder = Recorder(bus)
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={"MOTD": "antes"})
    deps = make_deps(runtime, config, bus)
    server_id = await make_running(deps, runtime)
    old_runtime = runtime.materialized[0]

    config.env["MOTD"] = "después"
    view = await ApplyConfigUseCase(deps, OperationGuard()).execute(
        ApplyConfigCommand(server_id=server_id, config_rev=2)
    )

    assert view.state == ServerState.STARTING
    assert runtime.removed[0][0] == old_runtime
    assert runtime.specs["r1"].environment["MOTD"] == "después"
    assert SERVER_CONFIG_CHANGED in recorder.types


async def test_apply_config_servidor_detenido_preserva_stopped() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={"MOTD": "antes"})
    deps = make_deps(runtime, config, bus)
    server_id = await make_running(deps, runtime)
    await StopServerUseCase(deps).execute(StopServerCommand(server_id=server_id))

    config.env["MOTD"] = "después"
    view = await ApplyConfigUseCase(deps, OperationGuard()).execute(
        ApplyConfigCommand(server_id=server_id, config_rev=3)
    )

    assert view.state == ServerState.STOPPED
    assert runtime.started == ["r0"]


async def test_apply_config_sin_cambio_no_recrea() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(env={}), bus)
    server_id = await make_running(deps, runtime)

    view = await ApplyConfigUseCase(deps, OperationGuard()).execute(
        ApplyConfigCommand(server_id=server_id, config_rev=1)
    )

    assert view.state == ServerState.RUNNING
    assert len(runtime.materialized) == 1


async def test_apply_config_con_level_name_inyecta_env_y_recrea() -> None:
    """``ApplyConfigCommand.level_name`` inyecta ``LEVEL_NAME`` y recrea (§22)."""
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(env={"MOTD": "antes"}), bus)
    server_id = await make_running(deps, runtime)

    view = await ApplyConfigUseCase(deps, OperationGuard()).execute(
        ApplyConfigCommand(server_id=server_id, level_name="MundoNuevo")
    )

    assert view.state == ServerState.STARTING
    assert runtime.specs["r1"].environment["LEVEL_NAME"] == "MundoNuevo"
    assert len(runtime.materialized) == 2


async def test_apply_config_sin_level_name_no_inyecta_env() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(env={"MOTD": "antes"}), bus)
    server_id = await make_running(deps, runtime)

    view = await ApplyConfigUseCase(deps, OperationGuard()).execute(
        ApplyConfigCommand(server_id=server_id)
    )

    assert view.state == ServerState.RUNNING
    assert "LEVEL_NAME" not in runtime.specs["r0"].environment
    assert len(runtime.materialized) == 1


async def test_change_version_publica_version_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = InProcessEventBus()
    recorder = Recorder(bus)
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(), bus)
    server_id = await make_running(deps, runtime)
    monkeypatch.setattr(
        spec_factory_module,
        "_local_bedrock_binary_exists",
        lambda *args, **kwargs: False,
    )

    view = await ChangeVersionUseCase(deps, OperationGuard()).execute(
        ChangeVersionCommand(server_id=server_id, version="1.21.1")
    )

    assert view.version == "1.21.1"
    assert runtime.specs["r1"].version == "1.21.1"
    assert runtime.specs["r1"].environment["VERSION"] == "1.21.1"
    assert SERVER_VERSION_CHANGED in recorder.types


async def test_operacion_sobre_servidor_inexistente() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(), bus)
    with pytest.raises(ServerNotFoundError):
        await StartServerUseCase(deps).execute(StartServerCommand(server_id="nope"))


async def test_start_sin_artefacto_materializado() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    deps = make_deps(runtime, FakeConfigurationReader(), bus)
    await deps.repository.save(
        Server(
            id=ServerId("srv-x"),
            name="X",
            spec=RuntimeSpec(image="i", version="1.20.0"),
            state=ServerState.CREATED,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    with pytest.raises(ServerNotMaterializedError):
        await StartServerUseCase(deps).execute(StartServerCommand(server_id="srv-x"))
