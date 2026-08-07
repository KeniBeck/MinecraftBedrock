"""Comandos y prioridades del dominio Console (Blueprint §3.8, §16.9).

``CommandPriority`` ordena la cola por servidor: los comandos de mayor
prioridad saltan la cola. Console no valida el contenido del comando (eso es
negocio); solo lo ordena y lo escribe en stdin.
"""

from __future__ import annotations

from enum import StrEnum


class CommandPriority(StrEnum):
    """Prioridad de un comando en la cola por servidor (mayor salta primero)."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

    @property
    def order(self) -> int:
        """Orden numérico ascendente (0 = más prioritario) para ``heapq``."""
        return _PRIORITY_ORDER[self]


_PRIORITY_ORDER: dict[CommandPriority, int] = {
    CommandPriority.CRITICAL: 0,
    CommandPriority.HIGH: 1,
    CommandPriority.NORMAL: 2,
    CommandPriority.LOW: 3,
}
