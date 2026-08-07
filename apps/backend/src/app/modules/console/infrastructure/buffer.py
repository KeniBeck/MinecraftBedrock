"""Buffer de logs en memoria (Fase B, sin BBDD).

Implementa ``ConsoleLogWriter``: lectura (puerto de dominio) y ``append``.
Sigue usándose en tests y como referente de comportamiento; en producción el
wiring usa ``PostgresConsoleLogStore`` (Fase A paso 2).
"""

from __future__ import annotations

from app.modules.console.domain.console_log import ConsoleLine, ConsoleLog


class InMemoryConsoleLogStore:
    """Almacena un ``ConsoleLog`` por servidor; no sobrevive a reinicios."""

    def __init__(self, max_lines: int = 1000) -> None:
        self._max_lines = max_lines
        self._logs: dict[str, ConsoleLog] = {}

    async def get(self, server_id: str) -> ConsoleLog:
        log = self._logs.get(server_id)
        if log is None:
            log = ConsoleLog(server_id=server_id, max_lines=self._max_lines)
            self._logs[server_id] = log
        return log

    async def append(self, server_id: str, line: str) -> ConsoleLine:
        """Añade una línea al buffer del servidor (crea el buffer si falta)."""
        log = await self.get(server_id)
        return log.append(line)
