"""Tests de ``PortAllocator`` y asignación de puertos en creación/eliminación."""

from __future__ import annotations

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.ports.runtime import ServerState
from app.modules.server.application.commands import CreateServerCommand, RemoveServerCommand
from app.modules.server.application.spec_factory import (
    PortAllocator,
    RuntimeSpecFactory,
    build_port_allocator,
)
from app.modules.server.application.use_cases import (
    CreateServerUseCase,
    OperationGuard,
    RemoveServerUseCase,
)
from app.modules.server.domain.errors import ServerPortExhaustedError
from app.modules.server.domain.server import ServerId
from tests.conftest import FakeConfigurationReader, FakeRuntime, FakeSettings, SequenceIds
from tests.test_server_use_cases import make_deps


def test_port_allocator_asigna_puertos_distintos_en_pool() -> None:
    allocator = PortAllocator(
        game_pool=range(19132, 19182),
        rcon_pool=range(25632, 25682),
    )
    game1, rcon1 = allocator.allocate(())
    game2, rcon2 = allocator.allocate({game1, game1 + 1, rcon1})
    assert game1 == 19132
    assert game2 == 19134
    assert rcon1 == 25575
    assert rcon2 == 25632
    assert game1 != game2
    assert rcon1 != rcon2


def test_port_allocator_respeta_par_consecutivo_ipv6() -> None:
    allocator = PortAllocator(game_pool=(19132, 19134), rcon_pool=(25632,))
    game, _ = allocator.allocate({19133})
    assert game == 19134


async def test_dos_servidores_reciben_puertos_distintos() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    settings = FakeSettings(
        {
            "server.port_pool.start": 19132,
            "server.port_pool.end": 19181,
            "server.rcon_port_pool.start": 25632,
            "server.rcon_port_pool.end": 25681,
        }
    )
    deps = make_deps(
        runtime,
        FakeConfigurationReader(),
        bus,
        ids=SequenceIds("srv-1", "srv-2", "srv-3"),
        settings_values=settings._values,
    )
    deps.spec_factory = RuntimeSpecFactory(settings, build_port_allocator(settings))

    await CreateServerUseCase(deps).execute(CreateServerCommand(name="Alpha"))
    await CreateServerUseCase(deps).execute(CreateServerCommand(name="Beta"))

    spec1 = runtime.specs["r0"]
    spec2 = runtime.specs["r1"]
    ports1 = set(spec1.ports.values())
    ports2 = set(spec2.ports.values())
    assert ports1.isdisjoint(ports2)
    assert spec1.ports["19132/udp"] == 19132
    assert spec2.ports["19132/udp"] == 19134
    assert spec1.ports["19133/udp"] == 19133
    assert spec2.ports["19133/udp"] == 19135


async def test_eliminar_servidor_libera_puertos_para_reutilizar() -> None:
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    settings = FakeSettings(
        {
            "server.port_pool.start": 19132,
            "server.port_pool.end": 19135,
            "server.rcon_port_pool.start": 25632,
            "server.rcon_port_pool.end": 25635,
        }
    )
    deps = make_deps(
        runtime,
        FakeConfigurationReader(),
        bus,
        ids=SequenceIds("srv-1", "srv-2", "srv-3"),
        settings_values=settings._values,
    )
    deps.spec_factory = RuntimeSpecFactory(settings, build_port_allocator(settings))
    guard = OperationGuard()

    first = await CreateServerUseCase(deps).execute(CreateServerCommand(name="Alpha"))
    await CreateServerUseCase(deps).execute(CreateServerCommand(name="Beta"))

    await RemoveServerUseCase(deps, guard).execute(RemoveServerCommand(server_id=first.id))

    removed = await deps.repository.get(ServerId(first.id))
    assert removed is not None
    assert removed.state is ServerState.REMOVED

    await CreateServerUseCase(deps).execute(CreateServerCommand(name="Gamma"))
    assert runtime.specs["r2"].ports["19132/udp"] == 19132


async def test_pool_agotado_lanza_error() -> None:
    allocator = PortAllocator(game_pool=(19132,), rcon_pool=(25632,))
    with pytest.raises(ServerPortExhaustedError):
        allocator.allocate({19132, 19133, 25575, 25632})
