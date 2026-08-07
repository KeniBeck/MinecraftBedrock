"""Almacén en memoria de ``MetricSample`` (MVP sin BBDD, Fase E/H Postgres).

Buffer circular por servidor: la retención acotada evita crecimiento sin límite
en la sesión; los consumidores (WS por servidor) leen las últimas muestras.
"""

from __future__ import annotations

from app.modules.monitoring.domain.metric_sample import MetricSample


class InMemoryMetricSampleStore:
    """``MetricSampleStorePort`` con buffer circular por servidor."""

    def __init__(self, max_per_server: int = 100) -> None:
        self._max_per_server = max_per_server
        self._samples: dict[str, list[MetricSample]] = {}

    async def record(self, sample: MetricSample) -> None:
        bucket = self._samples.setdefault(sample.server_id, [])
        bucket.append(sample)
        del bucket[: -self._max_per_server]

    async def recent(self, server_id: str, limit: int = 10) -> list[MetricSample]:
        return list(self._samples.get(server_id, [])[-limit:])
