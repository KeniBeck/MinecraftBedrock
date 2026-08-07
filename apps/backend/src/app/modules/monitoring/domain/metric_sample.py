"""Muestra temporal de estado/métricas de un servidor (TDD §11.3, Blueprint §5.3).

``MetricSample`` es un value object inmutable con las series temporales que
observa Monitoring: CPU/RAM/disk, jugadores, latencia y estado online/offline
del juego (fuente primaria: ping RakNet, independiente del runtime). La
persistencia durable (Postgres) queda diferida a Fase E/H; por ahora las
muestras viven en memoria y se entregan por WS.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SampleStatus(StrEnum):
    """Estado en vivo del juego (ping RakNet)."""

    ONLINE = "online"
    OFFLINE = "offline"


@dataclass(frozen=True, slots=True)
class MetricSample:
    """Instantánea de una serie temporal (TDD §11.3)."""

    server_id: str
    ts: datetime
    status: SampleStatus
    latency_ms: float
    players_online: int
    players_max: int
    cpu: float
    ram_mb: float
    disk_mb: float
