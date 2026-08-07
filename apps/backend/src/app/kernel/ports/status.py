"""Contrato ``StatusProbePort`` (Blueprint §4.4, TDD §11).

Ping RakNet UDP: fuente primaria del estado del juego, independiente del
runtime. Nunca bloquea el hilo principal (timeout estricto).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """Resultado de un ping RakNet (Blueprint §4.4)."""

    online: bool
    motd: str = ""
    version: str = ""
    protocol_version: int = 0
    players_online: int = 0
    players_max: int = 0
    latency_ms: float = 0.0


class StatusProbePort(Protocol):
    """Sondea el estado en vivo de un servidor Bedrock."""

    def probe(self, host: str, port: int, timeout: float = 2.0) -> ProbeResult:
        """Devuelve ``ProbeResult`` (online/offline) para host:puerto."""
