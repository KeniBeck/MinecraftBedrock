"""Contrato de escritura del buffer de consola (infraestructura).

``ConsoleLogWriter`` extiende el puerto de dominio ``ConsoleLogStorePort`` con
``append``: el path de escritura (stream de runtime → buffer) necesita persistir
líneas, algo que el puerto de lectura no declara. Vive en infraestructura porque
solo lo usan adaptadores (stream y stores); la aplicación sigue dependiendo del
puerto de dominio.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.console.domain.console_log import ConsoleLine
from app.modules.console.domain.repository import ConsoleLogStorePort


class ConsoleLogWriter(ConsoleLogStorePort, Protocol):
    """Almacén que además acepta nuevas líneas (stream → buffer)."""

    async def append(self, server_id: str, line: str) -> ConsoleLine:
        """Añade una línea y devuelve el registro con su ``seq`` (persistido)."""
        ...
