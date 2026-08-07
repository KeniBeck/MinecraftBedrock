"""Puerto de persistencia del buffer de logs (Blueprint §3.8, §16.9).

El buffer vive en memoria en Fase B (mismo criterio que
``InMemoryServerRepository``); una implementación durable llegará con el
storage general (Fase C). El puerto se declara ``async`` para que la
implementación futura (BBDD) sea intercambiable sin tocar consumidores.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.console.domain.console_log import ConsoleLog


class ConsoleLogStorePort(Protocol):
    """Almacén de buffers por servidor (get-or-create)."""

    async def get(self, server_id: str) -> ConsoleLog:
        """Devuelve el buffer del servidor, creándolo si no existe."""
