"""Cache de snapshots del poller (deduplicación del doble-inspect).

El doble-inspect (change-log §30) ocurría porque dos caminos independientes
polleaban el mismo contenedor cada 5 s: el ``BackgroundPoller.poll_all`` (fondo)
y el WS ``/monitoring/ws`` (que llamaba ``poll_server`` por su cuenta cuando
había un cliente). Ambos hacían ``get_state`` (inspect) + ``get_resources``
(stats) del mismo contenedor.

Este hub hace que **todos** los consumidores compartan una única pasada por
servidor dentro de la ventana ``poll_interval``:
- ``MonitoringFacade.poll_server`` devuelve el snapshot fresco si existe, y
  solo pollea cuando el cache está viejo/ausente.
- ``MonitoringFacade.poll_all`` recorre los servidores a través del mismo
  camino cacheado, así que el fondo y el WS nunca pollean el mismo servidor a
  la vez.

Sin poller de fondo (tests, ``monitoring_poller=None``), el hub queda vacío y el
WS pollea directamente (fallback) — los tests de integración del WS no cambian.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.modules.monitoring.application.polling import StatusSnapshot

_T = TypeVar("_T")

_PollCallable = Callable[[str], Awaitable[StatusSnapshot | None]]


class SnapshotHub:
    """Último snapshot por servidor + momento de poll (monotónico)."""

    def __init__(self) -> None:
        self._latest: dict[str, StatusSnapshot] = {}
        self._polled_at: dict[str, float] = {}

    def get(self, server_id: str) -> StatusSnapshot | None:
        return self._latest.get(server_id)

    def polled_at(self, server_id: str) -> float:
        return self._polled_at.get(server_id, 0.0)

    def put(self, server_id: str, snapshot: StatusSnapshot) -> None:
        self._latest[server_id] = snapshot
        self._polled_at[server_id] = time.monotonic()


async def poll_or_cached(
    hub: SnapshotHub,
    server_id: str,
    poller: _PollCallable,
    *,
    ttl_seconds: float,
) -> StatusSnapshot | None:
    """Devuelve el snapshot fresco del hub o lo pollea y lo cachea.

    Un snapshot se considera fresco si fue polleado hace menos de
    ``ttl_seconds``. Si el poller devuelve ``None`` (servidor inexistente), no
    se cachea.
    """
    age = time.monotonic() - hub.polled_at(server_id)
    if 0.0 <= age < ttl_seconds:
        cached = hub.get(server_id)
        if cached is not None:
            return cached
    snapshot = await poller(server_id)
    if snapshot is not None:
        hub.put(server_id, snapshot)
    return snapshot
