"""Tests del módulo Configuration (Fase D paso 10).

Cubren la vista de solo lectura (``ConfigurationReader`` para Server), la
actualización de properties (validación → revisión → ``CONFIG.CHANGED``) y la
integración con Server: el evento dispara ``ApplyConfigUseCase`` y Server
registra la revisión deseada/aplicada.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.modules.configuration.application.facade import ConfigurationFacade
from app.modules.configuration.domain.config_profile import ConfigProfile
from app.modules.configuration.domain.events import CONFIG_CHANGED_TOPIC
from app.modules.configuration.domain.property_schema import PropertySchema
from app.modules.configuration.infrastructure.memory import InMemoryConfigurationRepository
from app.modules.server.application.commands import CreateServerCommand
from app.modules.server.application.facade import ServerFacade
from app.modules.server.application.use_cases import CreateServerUseCase
from app.modules.server.domain.server import ServerId
from tests.conftest import FakeRuntime, FakeSettings, FakeTime
from tests.test_server_use_cases import make_deps

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class Recorder:
    """Suscriptor a ``config.changed`` que graba eventos."""

    def __init__(self, bus: InProcessEventBus) -> None:
        self.events: list[DomainEvent] = []
        bus.subscribe(CONFIG_CHANGED_TOPIC, self._record)

    async def _record(self, event: DomainEvent) -> None:
        self.events.append(event)


def make_facade(
    bus: InProcessEventBus,
    *,
    settings_values: dict[str, object] | None = None,
    repository: InMemoryConfigurationRepository | None = None,
) -> ConfigurationFacade:
    return ConfigurationFacade(
        repository=repository or InMemoryConfigurationRepository(),
        schema=PropertySchema(),
        bus=bus,
        settings=FakeSettings(settings_values),
        time=FakeTime(NOW),
    )


async def test_desired_config_devuelve_defaults_sin_perfil() -> None:
    facade = make_facade(InProcessEventBus())

    desired = await facade.desired_config("srv-1")

    assert desired.version == "LATEST"
    assert desired.environment == {"LEVEL_NAME": "Mi Mundo 1"}
    assert desired.config_rev == 0


async def test_desired_config_default_level_name_configurable() -> None:
    facade = make_facade(InProcessEventBus(), settings_values={"defaults.level_name": "Otro"})

    desired = await facade.desired_config("srv-1")

    assert desired.environment == {"LEVEL_NAME": "Otro"}


async def test_desired_config_con_perfil_sin_level_name_no_inyecta_default() -> None:
    """Con perfil, el default no pisa las properties del usuario (§7.2)."""
    facade = make_facade(InProcessEventBus())
    await facade.update_properties("srv-1", {"server-name": "Mi Mundo"})

    desired = await facade.desired_config("srv-1")

    assert desired.environment == {"SERVER_NAME": "Mi Mundo"}
    assert desired.config_rev == 1


async def test_update_properties_proyecta_a_env_y_mantiene_revision() -> None:
    facade = make_facade(InProcessEventBus())
    await facade.update_properties("srv-1", {"server-name": "Mi Mundo", "max-players": "12"})

    desired = await facade.desired_config("srv-1")

    assert desired.environment == {"SERVER_NAME": "Mi Mundo", "MAX_PLAYERS": "12"}
    assert desired.config_rev == 1


async def test_update_properties_proyecta_level_seed_y_view_distance() -> None:
    facade = make_facade(InProcessEventBus())
    await facade.update_properties(
        "srv-1",
        {"level-seed": "12345", "view-distance": "12"},
    )

    desired = await facade.desired_config("srv-1")

    assert desired.environment == {"LEVEL_SEED": "12345", "VIEW_DISTANCE": "12"}


async def test_update_properties_publica_config_changed_con_revision() -> None:
    bus = InProcessEventBus()
    recorder = Recorder(bus)
    facade = make_facade(bus)

    await facade.update_properties("srv-1", {"max-players": "10"}, actor_id="u1")
    await facade.update_properties("srv-1", {"max-players": "20"}, actor_id="u1")

    assert len(recorder.events) == 2
    event = recorder.events[-1]
    assert event.type == "CONFIG.CHANGED"
    assert event.server_id == "srv-1"
    assert event.payload == {"server_id": "srv-1", "config_rev": 2}
    assert event.actor_id == "u1"


async def test_update_properties_sin_cambios_no_publica_evento() -> None:
    bus = InProcessEventBus()
    recorder = Recorder(bus)
    facade = make_facade(bus)

    await facade.update_properties("srv-1", {"max-players": "10"})
    profile = await facade.update_properties("srv-1", {"max-players": "10"})

    assert profile.config_rev == 1
    assert len(recorder.events) == 1


async def test_update_properties_invalidas_son_rechazadas() -> None:
    facade = make_facade(InProcessEventBus())

    try:
        await facade.update_properties("srv-1", {"max-players": "100"})
    except ValueError as exc:
        assert "max-players" in str(exc)
    else:
        raise AssertionError("Expected validation error for max-players=100")


async def test_historial_append_only_con_actor() -> None:
    repository = InMemoryConfigurationRepository()
    facade = make_facade(InProcessEventBus(), repository=repository)

    await facade.update_properties("srv-1", {"gamemode": "creative"}, actor_id="u1")
    await facade.update_properties("srv-1", {"gamemode": "survival"}, actor_id="u2")

    history = await repository.history("srv-1")

    assert [entry.config_rev for entry in history] == [1, 2]
    assert history[-1].properties == {"gamemode": "survival"}
    assert history[-1].actor_id == "u2"


async def test_config_changed_desencadena_aplicacion_en_server() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    configuration = make_facade(bus)
    deps = make_deps(runtime, configuration, bus)
    facade = ServerFacade(
        repository=deps.repository,
        configuration=deps.configuration,
        spec_factory=deps.spec_factory,
        deps=deps,
    )
    facade.register_handlers()

    view = await CreateServerUseCase(deps).execute(CreateServerCommand(name="Survival"))
    await configuration.update_properties(view.id, {"server-name": "Mi Mundo", "max-players": "10"})

    server = await deps.repository.get_required(ServerId(view.id))
    assert server.desired_config_rev == 1
    assert server.applied_config_rev == 1
    assert server.spec.environment["SERVER_NAME"] == "Mi Mundo"


async def test_config_changed_no_publica_si_no_hay_perfil_previo_en_server_created() -> None:
    """La creación de servidor usa defaults; un update posterior revs=1."""
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    configuration = make_facade(bus)
    deps = make_deps(runtime, configuration, bus)
    facade = ServerFacade(
        repository=deps.repository,
        configuration=deps.configuration,
        spec_factory=deps.spec_factory,
        deps=deps,
    )
    facade.register_handlers()

    view = await CreateServerUseCase(deps).execute(CreateServerCommand(name="Survival"))
    created = await deps.repository.get_required(ServerId(view.id))
    assert created.desired_config_rev is None

    await configuration.update_properties(view.id, {"max-players": "8"})
    after = await deps.repository.get_required(ServerId(view.id))
    assert after.desired_config_rev == 1


async def test_get_profile_devuelve_none_sin_perfil() -> None:
    facade = make_facade(InProcessEventBus())

    assert await facade.get_profile("srv-9") is None


async def test_update_preserva_applied_existente() -> None:
    repository = InMemoryConfigurationRepository()
    bus = InProcessEventBus()
    facade = make_facade(bus, repository=repository)
    await facade.update_properties("srv-1", {"gamemode": "creative"})

    profile = await facade.get_profile("srv-1")
    assert profile is not None
    applied = ConfigProfile(
        server_id=profile.server_id,
        properties=dict(profile.properties),
        version=profile.version,
        config_rev=profile.config_rev,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        applied={"gamemode": "creative"},
        applied_at=NOW,
    )
    await repository.save_profile(applied)

    updated = await facade.update_properties("srv-1", {"gamemode": "survival"})

    assert updated.applied == {"gamemode": "creative"}
    assert updated.applied_at == NOW
