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
from app.kernel.logging import get_logger
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

logger = get_logger(__name__)


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
    def server(self) -> ServerFacade:
        """Facade de Server usada para listar/consultar servidores (para el hub)."""
        return self._server

    @property
    def probe_timeout(self) -> float:
        return float(cast(float, self._settings.get("monitoring.probe_timeout", 2.0)))

    @property
    def runtime_timeout(self) -> float:
        """Timeout de las llamadas síncronas al runtime/probe dentro del poller."""
        return float(cast(float, self._settings.get("monitoring.runtime_timeout", 5.0)))

    async def poll_server(self, server_id: str) -> StatusSnapshot | None:
        view = await self._server.get_server(server_id)
        if view is None:
            return None

        result = await self._probe_with_timeout(view)
        runtime_state, resources = await self._runtime_snapshot(view)
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

    def _probe_host(self, view: ServerView) -> str:
        """Host para el ping RakNet: ``monitoring.probe_host`` si está
        configurado, si no el host público de la conexión (``connection.host``)."""
        configured = self._settings.get("monitoring.probe_host", None)
        return str(configured) if configured else view.connection.host

    async def _probe_with_timeout(self, view: ServerView) -> ProbeResult:
        """Ping RakNet (síncrono) en un hilo, cortado a ``runtime_timeout``.

        El probe es síncrono (sockets de bloqueo); se ejecuta en
        ``asyncio.to_thread`` para no bloquear el event loop y se corta con
        ``asyncio.wait_for``. Si excede el límite, la muestra se reporta como
        offline (timeout del probe ≠ juego caído, pero el WS no se congela).
        """
        host = self._probe_host(view)
        port = view.connection.port
        timeout = self.probe_timeout
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._probe.probe, host, port, timeout),
                timeout=self.runtime_timeout,
            )
        except TimeoutError:
            logger.warning(
                "monitoring: probe timeout para %s (%s:%s) tras %.1fs",
                view.id,
                host,
                port,
                self.runtime_timeout,
            )
            return ProbeResult(online=False)

    async def _runtime_snapshot(
        self, view: ServerView
    ) -> tuple[RuntimeState | None, dict[str, Any]]:
        """Estado y recursos del runtime, cada uno en un hilo con timeout.

        ``get_state``/``get_resources`` son síncronos (docker-py) y pueden
        bloquear hasta ``docker_timeout`` (300 s). Se ejecutan en
        ``asyncio.to_thread`` (no congelan el event loop) y se cortan a
        ``runtime_timeout`` (5 s): si el daemon no responde, se descarta la
        muestra de esa pasada (estado ``None``/recursos ``{}``) y el poller
        sigue.
        """
        if view.runtime_id is None:
            return None, {}
        try:
            state = await asyncio.wait_for(
                asyncio.to_thread(self._runtime.get_state, view.runtime_id),
                timeout=self.runtime_timeout,
            )
        except TimeoutError:
            logger.warning(
                "monitoring: get_state timeout para server %s tras %.1fs",
                view.id,
                self.runtime_timeout,
            )
            return None, {}
        except AppError:
            return None, {}

        try:
            resources = await asyncio.wait_for(
                asyncio.to_thread(self._runtime.get_resources, view.runtime_id),
                timeout=self.runtime_timeout,
            )
        except TimeoutError:
            logger.warning(
                "monitoring: get_resources timeout para server %s tras %.1fs",
                view.id,
                self.runtime_timeout,
            )
            return state, {}
        except AppError:
            return state, {}

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
        cpu = resources.get("cpu_percent")
        return MetricSample(
            server_id=view.id,
            ts=self._time.now(),
            status=SampleStatus.ONLINE if result.online else SampleStatus.OFFLINE,
            latency_ms=result.latency_ms,
            players_online=result.players_online,
            players_max=result.players_max,
            cpu=float(cpu) if cpu is not None else None,
            ram_mb=_bytes_to_mb(resources.get("memory_usage_bytes")),
            disk_mb=0.0,
        )
