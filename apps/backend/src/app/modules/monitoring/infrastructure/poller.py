"""Tarea de fondo del poller de estado (Blueprint §16.11).

El panel arranca el poller en el lifespan de la app (producción). Los tests
usan ``monitoring_poller=None`` en el ``Container`` y el WS por servidor
funciona como driver del poll, de modo que el bucle de fondo no corre bajo
``TestClient``.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.modules.monitoring.application.facade import MonitoringFacade

logger = logging.getLogger(__name__)


class BackgroundPoller:
    """Bucle asíncrono que ejecuta ``poll_all`` cada ``interval`` segundos."""

    def __init__(self, facade: MonitoringFacade, *, interval: float = 5.0) -> None:
        self._facade = facade
        self._interval = interval
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self._facade.poll_all(stagger=0.2)
            except Exception:  # noqa: BLE001 — el bucle no debe morir por un tick
                logger.exception("El poller de estado falló en este tick")
            await asyncio.sleep(self._interval)
