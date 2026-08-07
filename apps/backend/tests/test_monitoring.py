"""Tests unitarios del módulo Monitoring (poller de estado, Fase D paso 9).

Verifican la reconciliación de estado (Monitoring detecta, Server decide vía
``mark_started``/``mark_crashed``) y el registro de ``MetricSample`` en el
almacén en memoria.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.ports.runtime import ServerState
from app.kernel.ports.status import ProbeResult
from app.modules.monitoring.application.polling import StatusPoller
from app.modules.monitoring.domain.metric_sample import SampleStatus
from app.modules.monitoring.infrastructure.memory import InMemoryMetricSampleStore
from app.modules.server.application.commands import (
    CreateServerCommand,
    RemoveServerCommand,
    StartServerCommand,
)
from app.modules.server.application.facade import ServerFacade
from app.modules.server.application.use_cases import (
    CreateServerUseCase,
    MarkStartedUseCase,
    ServerDeps,
    StartServerUseCase,
)
from tests.conftest import FakeConfigurationReader, FakeRuntime, FakeSettings, FakeTime
from tests.test_server_use_cases import make_deps

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakeProbe:
    """``StatusProbePort`` con resultado mutable inyectado."""

    def __init__(self, result: ProbeResult) -> None:
        self.result = result
        self.calls: list[tuple[str, int]] = []

    def probe(self, host: str, port: int, timeout: float = 2.0) -> ProbeResult:
        del timeout
        self.calls.append((host, port))
        return self.result


class Harness:
    """Facade de Server + runtime/probe fake + poller listos para usar."""

    def __init__(self) -> None:
        self.bus = InProcessEventBus()
        self.runtime = FakeRuntime()
        self.deps: ServerDeps = make_deps(self.runtime, FakeConfigurationReader(), self.bus)
        self.facade = make_facade(self.deps)
        self.probe = FakeProbe(ProbeResult(online=True, latency_ms=5.0))
        self.store = InMemoryMetricSampleStore(max_per_server=10)
        self.poller = make_poller(self.facade, self.runtime, self.probe, store=self.store)

    async def create_started(self) -> str:
        view = await CreateServerUseCase(self.deps).execute(CreateServerCommand(name="Survival"))
        await StartServerUseCase(self.deps).execute(StartServerCommand(server_id=view.id))
        return view.id


def make_facade(deps: ServerDeps) -> ServerFacade:
    facade = ServerFacade(
        repository=deps.repository,
        configuration=deps.configuration,
        spec_factory=deps.spec_factory,
        deps=deps,
    )
    facade.register_handlers()
    return facade


def make_poller(
    facade: ServerFacade,
    runtime: FakeRuntime,
    probe: FakeProbe,
    *,
    store: InMemoryMetricSampleStore | None = None,
    settings_values: dict[str, object] | None = None,
) -> StatusPoller:
    return StatusPoller(
        server=facade,
        runtime=runtime,
        probe=probe,
        store=store or InMemoryMetricSampleStore(),
        time=FakeTime(NOW),
        settings=FakeSettings(settings_values),
    )


async def test_poll_confirma_arranque_cuando_el_juego_responde() -> None:
    h = Harness()
    server_id = await h.create_started()

    snapshot = await h.poller.poll_server(server_id)

    view = await h.facade.get_server(server_id)
    assert view is not None
    assert snapshot is not None
    assert snapshot.state is ServerState.RUNNING
    assert view.state is ServerState.RUNNING
    assert snapshot.sample.status.value == "online"


async def test_poll_marca_crashed_cuando_el_juego_no_responde_y_el_runtime_esta_muerto() -> None:
    h = Harness()
    server_id = await h.create_started()
    await MarkStartedUseCase(h.deps).execute(server_id)
    view = await h.facade.get_server(server_id)
    assert view is not None and view.runtime_id is not None
    h.runtime.stop(view.runtime_id)
    h.probe.result = ProbeResult(online=False, latency_ms=200.0)

    snapshot = await h.poller.poll_server(server_id)

    assert snapshot is not None
    assert snapshot.state is ServerState.CRASHED
    updated = await h.facade.get_server(server_id)
    assert updated is not None and updated.state is ServerState.CRASHED


async def test_poll_no_marca_crashed_si_el_runtime_sigue_vivo() -> None:
    h = Harness()
    server_id = await h.create_started()
    await MarkStartedUseCase(h.deps).execute(server_id)
    h.probe.result = ProbeResult(online=False, latency_ms=200.0)

    snapshot = await h.poller.poll_server(server_id)

    assert snapshot is not None
    assert snapshot.state is ServerState.RUNNING
    updated = await h.facade.get_server(server_id)
    assert updated is not None and updated.state is ServerState.RUNNING


async def test_poll_no_reconcilia_servidor_recien_creado() -> None:
    h = Harness()
    view = await CreateServerUseCase(h.deps).execute(CreateServerCommand(name="Survival"))

    snapshot = await h.poller.poll_server(view.id)

    assert snapshot is not None
    assert snapshot.state is ServerState.CREATED
    assert snapshot.sample.status.value == "online"


async def test_poll_registra_muestra_y_el_store_esta_acotado() -> None:
    h = Harness()
    server_id = await h.create_started()
    for _ in range(25):
        await h.poller.poll_server(server_id)

    recent = await h.store.recent(server_id, limit=10)

    assert len(recent) == 10
    assert recent[-1].server_id == server_id
    assert await h.store.recent("srv-otro") == []


async def test_poll_all_omite_servidores_eliminados() -> None:
    h = Harness()
    view = await CreateServerUseCase(h.deps).execute(CreateServerCommand(name="Survival"))
    await h.facade.remove(RemoveServerCommand(server_id=view.id))

    snapshots = await h.poller.poll_all()

    assert snapshots == []


async def test_sample_status_offline_cuando_el_ping_falla() -> None:
    h = Harness()
    server_id = await h.create_started()
    await MarkStartedUseCase(h.deps).execute(server_id)
    h.probe.result = ProbeResult(online=False, latency_ms=200.0)

    snapshot = await h.poller.poll_server(server_id)

    assert snapshot is not None
    assert snapshot.sample.status is SampleStatus.OFFLINE
