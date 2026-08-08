"""Tarea de fondo del reloj del Scheduler (Blueprint §16.11).

Mismo patrón que ``BackgroundPoller`` de Monitoring: un bucle asíncrono que
ejecuta ``tick`` cada ``interval`` segundos. Se arranca en el lifespan de la
app (producción); los tests usan ``scheduler_poller=None`` en el ``Container``
y llaman a la facade ``tick`` directamente.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.modules.scheduler.application.facade import SchedulerFacade

logger = logging.getLogger(__name__)


class SchedulerPoller:
    """Bucle asíncrono que evalúa tareas programadas cada ``interval`` segundos."""

    def __init__(self, facade: SchedulerFacade, *, interval: float = 5.0) -> None:
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
                await self._facade.tick()
            except Exception:  # noqa: BLE001 — el bucle no debe morir por un tick
                logger.exception("El tick del Scheduler falló en esta vuelta")
            await asyncio.sleep(self._interval)
