"""Tests de los handlers de eventos del módulo Server (Blueprint §3.2)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import RuntimeSpec, ServerState
from app.modules.server.application.handlers import (
    AllowlistToggledHandler,
    ConfigChangedHandler,
    WorldActivatedHandler,
)
from app.modules.server.application.spec_factory import RuntimeSpecFactory
from app.modules.server.application.use_cases import ApplyConfigUseCase, OperationGuard, ServerDeps
from app.modules.server.domain.events import (
    ALLOWLIST_TOGGLED_TOPIC,
    CONFIG_CHANGED_TOPIC,
    WORLD_ACTIVATED_TOPIC,
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


def make_harness(
    bus: InProcessEventBus,
    config: FakeConfigurationReader,
    runtime: FakeRuntime,
) -> tuple[ApplyConfigUseCase, ServerDeps]:
    settings = FakeSettings()
    spec_factory = RuntimeSpecFactory(settings)
    deps = ServerDeps(
        repository=InMemoryServerRepository(),
        runtime=runtime,
        bus=bus,
        ids=SequenceIds("srv-1"),
        time=FakeTime(NOW),
        settings=settings,
        configuration=config,
        spec_factory=spec_factory,
    )
    return ApplyConfigUseCase(deps, OperationGuard()), deps


async def seed(deps: ServerDeps) -> None:
    await deps.repository.save(
        Server(
            id=ServerId("srv-1"),
            name="Survival",
            spec=RuntimeSpec(image="i", version="1.20.0", environment={"MOTD": "viejo"}),
            state=ServerState.STOPPED,
            created_at=NOW,
            updated_at=NOW,
        )
    )


async def test_config_changed_replica_config_deseada() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={"MOTD": "viejo"})
    apply_config, deps = make_harness(bus, config, runtime)
    await seed(deps)
    bus.subscribe(CONFIG_CHANGED_TOPIC, ConfigChangedHandler(apply_config))

    config.env["MOTD"] = "nuevo"
    await bus.publish(
        DomainEvent(type="CONFIG.CHANGED", server_id="srv-1", payload={"config_rev": 5})
    )

    server = await deps.repository.get_required(ServerId("srv-1"))
    assert server.spec.environment["MOTD"] == "nuevo"
    assert server.applied_config_rev == 5


async def test_world_activated_replica_config_deseada() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={"MOTD": "viejo"})
    apply_config, deps = make_harness(bus, config, runtime)
    await seed(deps)
    bus.subscribe(WORLD_ACTIVATED_TOPIC, WorldActivatedHandler(apply_config))

    config.env["MOTD"] = "otro"
    await bus.publish(
        DomainEvent(type="WORLD.ACTIVATED", server_id="srv-1", payload={"config_rev": 3})
    )

    server = await deps.repository.get_required(ServerId("srv-1"))
    assert server.spec.environment["MOTD"] == "otro"
    assert server.applied_config_rev == 3


async def test_world_activated_sin_config_rev_no_pisa_la_revision() -> None:
    """``WORLD.ACTIVATED`` no lleva ``config_rev`` (§22): se reaplica sin cambiarla."""
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={"MOTD": "viejo"})
    apply_config, deps = make_harness(bus, config, runtime)
    await seed(deps)
    bus.subscribe(CONFIG_CHANGED_TOPIC, ConfigChangedHandler(apply_config))
    bus.subscribe(WORLD_ACTIVATED_TOPIC, WorldActivatedHandler(apply_config))

    await bus.publish(
        DomainEvent(type="CONFIG.CHANGED", server_id="srv-1", payload={"config_rev": 5})
    )
    config.env["MOTD"] = "otro"
    await bus.publish(DomainEvent(type="WORLD.ACTIVATED", server_id="srv-1"))

    server = await deps.repository.get_required(ServerId("srv-1"))
    assert server.spec.environment["MOTD"] == "otro"
    assert server.applied_config_rev == 5


async def test_world_activated_inyecta_level_name_del_mundo_activado() -> None:
    """``WORLD.ACTIVATED`` propaga el ``name`` como env ``LEVEL_NAME`` (§7.2, §22)."""
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={"MOTD": "viejo"})
    apply_config, deps = make_harness(bus, config, runtime)
    await seed(deps)
    bus.subscribe(WORLD_ACTIVATED_TOPIC, WorldActivatedHandler(apply_config))

    await bus.publish(
        DomainEvent(
            type="WORLD.ACTIVATED",
            server_id="srv-1",
            payload={"name": "MundoNuevo", "level_name": "MundoNuevo"},
        )
    )

    server = await deps.repository.get_required(ServerId("srv-1"))
    assert server.spec.environment["LEVEL_NAME"] == "MundoNuevo"
    assert runtime.materialized, "el spec cambió → el contenedor debe recrearse"


async def test_world_activated_creado_sin_name_mantiene_el_actual() -> None:
    """Sin ``name`` en el payload no se pisa el ``LEVEL_NAME`` existente."""
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={"MOTD": "viejo", "LEVEL_NAME": "Actual"})
    apply_config, deps = make_harness(bus, config, runtime)
    await seed(deps)
    bus.subscribe(WORLD_ACTIVATED_TOPIC, WorldActivatedHandler(apply_config))

    await bus.publish(DomainEvent(type="WORLD.ACTIVATED", server_id="srv-1"))

    server = await deps.repository.get_required(ServerId("srv-1"))
    assert server.spec.environment["LEVEL_NAME"] == "Actual"
    assert server.applied_config_rev is None


async def test_allowlist_toggled_inyecta_env_true_y_recrea() -> None:
    """``PERMISSION.ALLOWLIST_TOGGLED`` propaga ``enabled`` como ``ALLOW_LIST=true``."""
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={"MOTD": "viejo"})
    apply_config, deps = make_harness(bus, config, runtime)
    await seed(deps)
    bus.subscribe(ALLOWLIST_TOGGLED_TOPIC, AllowlistToggledHandler(apply_config))

    await bus.publish(
        DomainEvent(
            type="PERMISSION.ALLOWLIST_TOGGLED", server_id="srv-1", payload={"enabled": True}
        )
    )

    server = await deps.repository.get_required(ServerId("srv-1"))
    assert server.spec.environment["ALLOW_LIST"] == "true"
    assert runtime.materialized, "el spec cambió → el contenedor debe recrearse"
    assert server.applied_config_rev is None


async def test_allowlist_toggled_false_inyecta_env_false() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={"ALLOW_LIST": "true"})
    apply_config, deps = make_harness(bus, config, runtime)
    await seed(deps)
    bus.subscribe(ALLOWLIST_TOGGLED_TOPIC, AllowlistToggledHandler(apply_config))

    await bus.publish(
        DomainEvent(
            type="PERMISSION.ALLOWLIST_TOGGLED", server_id="srv-1", payload={"enabled": False}
        )
    )

    server = await deps.repository.get_required(ServerId("srv-1"))
    assert server.spec.environment["ALLOW_LIST"] == "false"


async def test_allowlist_toggled_sin_enabled_mantiene_el_actual() -> None:
    """Sin ``enabled`` en el payload no se pisa el ``ALLOW_LIST`` existente."""
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={"ALLOW_LIST": "true"})
    apply_config, deps = make_harness(bus, config, runtime)
    await seed(deps)
    bus.subscribe(ALLOWLIST_TOGGLED_TOPIC, AllowlistToggledHandler(apply_config))

    await bus.publish(DomainEvent(type="PERMISSION.ALLOWLIST_TOGGLED", server_id="srv-1"))

    server = await deps.repository.get_required(ServerId("srv-1"))
    assert server.spec.environment["ALLOW_LIST"] == "true"
    assert server.applied_config_rev is None


async def test_config_changed_sin_server_id_se_ignora() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    config = FakeConfigurationReader(env={})
    apply_config, _ = make_harness(bus, config, runtime)
    bus.subscribe(CONFIG_CHANGED_TOPIC, ConfigChangedHandler(apply_config))

    await bus.publish(DomainEvent(type="CONFIG.CHANGED", payload={"config_rev": 1}))

    assert runtime.materialized == []
