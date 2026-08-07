"""Poller de estado de servidores (Blueprint §3.10, §5.3, §16.11).

Monitoring solo observa y notifica: cada pasada consulta el ``StatusProbePort``
(ping RakNet, independiente del runtime) y el ``ServerRuntimePort`` (estado,
salud y recursos) y, cuando la máquina de estados del dominio lo admite,
confirma arranques y caídas sobre la facade de Server (``mark_started`` /
``mark_crashed``). Las transiciones inválidas lanzan ``ServerStateError`` y se
ignoran: el estado de dominio sigue siendo la fuente de verdad.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

from app.kernel.errors import AppError
from app.kernel.ports.runtime import (
    RuntimeState,
    ServerRuntimePort,
    ServerState,
)
from app.kernel.ports.settings import SettingsPort
from app.kernel.ports.status import ProbeResult, StatusProbePort
from app.kernel.time import TimeProviderPort
from app.modules.monitoring.domain.metric_sample import MetricSample, SampleStatus
from app.modules.monitoring.domain.repository import MetricSampleStorePort
from app.modules.server.application.facade import ServerFacade
from app.modules.server.application.results import ServerView
from app.modules.server.domain.errors import ServerStateError

# Estados del runtime que indican proceso muerto sin parada controlada: si
# además el juego no responde al ping, Monitoring lo reporta como caído.
_DEAD_RUNTIME_STATES = frozenset({RuntimeState.STOPPED, RuntimeState.DYING, RuntimeState.ABSENT})


def _bytes_to_mb(value: object) -> float:
    try:
        return float(cast(Any, value)) / (1024 * 1024)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True, slots=True)
class StatusSnapshot:
    """Resultado de una pasada de poll: muestra + estado de dominio."""

    sample: MetricSample
    state: ServerState


class StatusPoller:
    """Una pasada de poll por servidor: sondea, reconcilia y registra."""

    def __init__(
        self,
        server: ServerFacade,
        runtime: ServerRuntimePort,
        probe: StatusProbePort,
        store: MetricSampleStorePort,
        time: TimeProviderPort,
        settings: SettingsPort,
    ) -> None:
        self._server = server
        self._runtime = runtime
        self._probe = probe
        self._store = store
        self._time = time
        self._settings = settings

    @property
    def probe_timeout(self) -> float:
        return float(cast(float, self._settings.get("monitoring.probe_timeout", 2.0)))

    async def poll_server(self, server_id: str) -> StatusSnapshot | None:
        view = await self._server.get_server(server_id)
        if view is None:
            return None

        result = self._probe.probe(
            view.connection.host,
            view.connection.port,
            timeout=self.probe_timeout,
        )
        runtime_state, resources = self._runtime_snapshot(view)
        await self._reconcile(view, result, runtime_state)

        refreshed = await self._server.get_server(server_id)
        state = refreshed.state if refreshed is not None else view.state
        sample = self._build_sample(view, result, resources)
        await self._store.record(sample)
        return StatusSnapshot(sample=sample, state=state)

    async def poll_all(self, *, stagger: float = 0.0) -> list[StatusSnapshot]:
        """Polla todos los servidores no eliminados (poller de fondo)."""
        snapshots: list[StatusSnapshot] = []
        views = await self._server.list_servers()
        for view in views:
            if view.state is ServerState.REMOVED:
                continue
            snapshot = await self.poll_server(view.id)
            if snapshot is not None:
                snapshots.append(snapshot)
            if stagger:
                await asyncio.sleep(stagger)
        return snapshots

    def _runtime_snapshot(self, view: ServerView) -> tuple[RuntimeState | None, dict[str, Any]]:
        if view.runtime_id is None:
            return None, {}
        try:
            state = self._runtime.get_state(view.runtime_id)
            resources = self._runtime.get_resources(view.runtime_id)
        except AppError:
            return None, {}
        return state, resources

    async def _reconcile(
        self,
        view: ServerView,
        result: ProbeResult,
        runtime_state: RuntimeState | None,
    ) -> None:
        if view.state not in (ServerState.STARTING, ServerState.RUNNING):
            return
        try:
            if view.state is ServerState.STARTING and result.online:
                await self._server.mark_started(view.id)
                return
            if not result.online and runtime_state in _DEAD_RUNTIME_STATES:
                await self._server.mark_crashed(view.id)
        except ServerStateError:
            return

    def _build_sample(
        self,
        view: ServerView,
        result: ProbeResult,
        resources: dict[str, Any],
    ) -> MetricSample:
        return MetricSample(
            server_id=view.id,
            ts=self._time.now(),
            status=SampleStatus.ONLINE if result.online else SampleStatus.OFFLINE,
            latency_ms=result.latency_ms,
            players_online=result.players_online,
            players_max=result.players_max,
            cpu=float(resources.get("cpu_percent") or 0.0),
            ram_mb=_bytes_to_mb(resources.get("memory_usage_bytes")),
            disk_mb=0.0,
        )
