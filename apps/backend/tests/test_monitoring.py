"""Tests unitarios del módulo Monitoring (poller de estado, Fase D paso 9).

Verifican la reconciliación de estado (Monitoring detecta, Server decide vía
``mark_started``/``mark_crashed``) y el registro de ``MetricSample`` en el
almacén en memoria.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.ports.runtime import ServerState
from app.kernel.ports.status import ProbeResult
from app.modules.monitoring.application.polling import StatusPoller, StatusSnapshot
from app.modules.monitoring.application.snapshot_hub import SnapshotHub, poll_or_cached
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


async def test_poll_usa_host_de_probe_configurado_si_existe() -> None:
    h = Harness()
    h.poller = make_poller(
        h.facade,
        h.runtime,
        h.probe,
        store=h.store,
        settings_values={"monitoring.probe_host": "172.18.0.1"},
    )
    server_id = await h.create_started()

    await h.poller.poll_server(server_id)

    assert h.probe.calls and h.probe.calls[0][0] == "172.18.0.1"


async def test_poll_cae_al_host_publico_si_no_hay_probe_host() -> None:
    h = Harness()
    server_id = await h.create_started()

    await h.poller.poll_server(server_id)

    assert h.probe.calls and h.probe.calls[0][0] == "localhost"


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


# --- dedup del doble-inspect (SnapshotHub) ---------------------------------


async def test_poll_or_cached_polleo_una_vez_dentro_de_la_ventana() -> None:
    h = Harness()
    server_id = await h.create_started()
    hub = SnapshotHub()
    calls: list[str] = []

    async def fake_poller(sid: str) -> StatusSnapshot | None:
        calls.append(sid)
        return await h.poller.poll_server(sid)

    first = await poll_or_cached(hub, server_id, fake_poller, ttl_seconds=5.0)
    second = await poll_or_cached(hub, server_id, fake_poller, ttl_seconds=5.0)

    assert first is not None and second is not None
    assert calls == [server_id]  # el segundo golpe usa el cache, no vuelve a pollear


async def test_poll_or_cached_no_cachea_cuando_poller_devuelve_none() -> None:
    hub = SnapshotHub()
    calls: list[str] = []

    async def missing_poller(sid: str) -> StatusSnapshot | None:
        calls.append(sid)
        return None

    assert await poll_or_cached(hub, "srv-x", missing_poller, ttl_seconds=5.0) is None
    assert await poll_or_cached(hub, "srv-x", missing_poller, ttl_seconds=5.0) is None
    assert calls == ["srv-x", "srv-x"]


async def test_facade_poll_server_y_poll_all_comparten_una_pasada() -> None:
    """El fondo y el WS no duplican el poll del mismo servidor en la ventana."""
    from app.modules.monitoring.application.facade import MonitoringFacade

    h = Harness()
    server_id = await h.create_started()
    facade = MonitoringFacade(h.poller, poll_interval=5.0)
    h.probe.calls = []

    # El WS pollea el servidor activo…
    ws_snapshot = await facade.poll_server(server_id)
    assert ws_snapshot is not None

    # …y el poll del fondo, que corre enseguida, reutiliza el snapshot cacheado.
    all_snapshots = await facade.poll_all()
    assert [s.sample.server_id for s in all_snapshots] == [server_id]
    assert len(h.probe.calls) == 1  # una sola pasada, no dos


# --- timeout de llamadas síncronas al runtime (no bloquean el event loop) ---


class SlowRuntime(FakeRuntime):
    """``ServerRuntimePort`` cuyas llamadas síncronas tardan más que el timeout.

    Se ejecutan en un hilo (``asyncio.to_thread``) y ``asyncio.wait_for`` las
    corta a ``monitoring.runtime_timeout``; el poller continúa con valores
    ``None``/``{}`` en vez de congelar el event loop.
    """

    def get_state(self, runtime_id: str):
        time.sleep(0.3)
        return super().get_state(runtime_id)

    def get_resources(self, runtime_id: str):
        time.sleep(0.3)
        return super().get_resources(runtime_id)


async def test_poll_corta_get_state_timeout_sin_bloquear() -> None:
    h = Harness()
    slow = SlowRuntime()
    poller = make_poller(
        h.facade,
        slow,
        h.probe,
        store=h.store,
        settings_values={"monitoring.runtime_timeout": 0.05},
    )
    server_id = await h.create_started()

    snapshot = await poller.poll_server(server_id)

    # El timeout se cortó (0.3s de sleep > 0.05s de límite) sin congelar el WS.
    assert snapshot is not None
    # get_state devolvió None por timeout → sin estado de runtime para reconciliar.
    assert snapshot.state is not None


async def test_poll_descarta_recursos_tras_timeout_de_get_resources() -> None:
    h = Harness()
    slow = SlowRuntime()
    poller = make_poller(
        h.facade,
        slow,
        h.probe,
        store=h.store,
        settings_values={"monitoring.runtime_timeout": 0.05},
    )
    server_id = await h.create_started()

    snapshot = await poller.poll_server(server_id)

    assert snapshot is not None
    assert snapshot.sample.cpu is None
    assert snapshot.sample.ram_mb == 0.0


async def test_poll_no_supera_el_timeout_total_de_la_pasada() -> None:
    """Una pasada con runtime lento termina en ~timeout, no en los 0.3s del sleep."""
    h = Harness()
    slow = SlowRuntime()
    poller = make_poller(
        h.facade,
        slow,
        h.probe,
        store=h.store,
        settings_values={"monitoring.runtime_timeout": 0.05},
    )
    server_id = await h.create_started()

    started = time.monotonic()
    snapshot = await poller.poll_server(server_id)
    elapsed = time.monotonic() - started

    assert snapshot is not None
    # get_state + get_resources, cada una cortada a 0.05s → la pasada total debe
    # estar muy por debajo de los 0.3s que tardaría el runtime sin el timeout.
    assert elapsed < 0.25
