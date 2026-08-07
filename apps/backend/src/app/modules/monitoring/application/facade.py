"""Facade pública del módulo Monitoring (Blueprint §3.10).

Solo observa: expone las pasadas de poll (per-servidor y global) que producen
``StatusSnapshot``. Las transiciones de estado las confirma Server cuando el
poller las detecta (los eventos ``SERVER.*`` los publica Server); Monitoring no
publica telemetría nueva en el bus: el envelope WS ``SERVER.STATE`` es solo
transporte (ADR-002).
"""

from __future__ import annotations

from app.modules.monitoring.application.polling import StatusPoller, StatusSnapshot


class MonitoringFacade:
    """Puerta de entrada del módulo Monitoring."""

    def __init__(self, poller: StatusPoller, *, poll_interval: float = 5.0) -> None:
        self._poller = poller
        self.poll_interval = poll_interval

    async def poll_server(self, server_id: str) -> StatusSnapshot | None:
        return await self._poller.poll_server(server_id)

    async def poll_all(self, *, stagger: float = 0.0) -> list[StatusSnapshot]:
        return await self._poller.poll_all(stagger=stagger)
