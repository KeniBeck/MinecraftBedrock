"""Puerto de persistencia de ``MetricSample`` (Blueprint §5.3).

En esta iteración la implementación es en memoria; el puerto es ``async`` para
que la tabla Postgres (Fase E/H) sea intercambiable sin tocar consumidores.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.monitoring.domain.metric_sample import MetricSample


class MetricSampleStorePort(Protocol):
    """Almacén append-only de muestras por servidor."""

    async def record(self, sample: MetricSample) -> None:
        """Persiste una muestra."""

    async def recent(self, server_id: str, limit: int = 10) -> list[MetricSample]:
        """Devuelve las últimas ``limit`` muestras del servidor (cronológicas)."""
