"""Facade pública del módulo Monitoring (Blueprint §3.10).

Solo observa: expone las pasadas de poll (per-servidor y global) que producen
``StatusSnapshot``. Las transiciones de estado las confirma Server cuando el
poller las detecta (los eventos ``SERVER.*`` los publica Server); Monitoring no
publica telemetría nueva en el bus: el envelope WS ``SERVER.STATE`` es solo
transporte (ADR-002).

Todos los consumidores (WS por servidor y poller de fondo) pasan por el
``SnapshotHub``: una única pasada por servidor dentro de ``poll_interval``
(dedup del doble-inspect, change-log §30).
"""

from __future__ import annotations

import asyncio

from app.kernel.ports.runtime import ServerState
from app.modules.monitoring.application.polling import StatusPoller, StatusSnapshot
from app.modules.monitoring.application.snapshot_hub import SnapshotHub, poll_or_cached


class MonitoringFacade:
    """Puerta de entrada del módulo Monitoring."""

    def __init__(
        self,
        poller: StatusPoller,
        *,
        poll_interval: float = 5.0,
        hub: SnapshotHub | None = None,
    ) -> None:
        self._poller = poller
        self.poll_interval = poll_interval
        self._hub = hub or SnapshotHub()

    async def poll_server(self, server_id: str) -> StatusSnapshot | None:
        """Snapshot fresco de un servidor, cacheado dentro de ``poll_interval``.

        Si ya hay un snapshot reciente (lo polleó el fondo o el propio WS hace
        menos de ``poll_interval``), se devuelve sin tocar Docker otra vez.
        """
        return await poll_or_cached(
            self._hub,
            server_id,
            self._poller.poll_server,
            ttl_seconds=self.poll_interval,
        )

    async def poll_all(self, *, stagger: float = 0.0) -> list[StatusSnapshot]:
        """Polla todos los servidores no eliminados compartiendo el hub.

        El fondo (``BackgroundPoller``) y el WS usan el mismo camino cacheado,
        así que un servidor solo se pollea una vez por ventana aunque ambos
        corran a la vez.
        """
        snapshots: list[StatusSnapshot] = []
        views = await self._poller.server.list_servers()
        for view in views:
            if view.state is ServerState.REMOVED:
                continue
            snapshot = await self.poll_server(view.id)
            if snapshot is not None:
                snapshots.append(snapshot)
            if stagger:
                await asyncio.sleep(stagger)
        return snapshots
