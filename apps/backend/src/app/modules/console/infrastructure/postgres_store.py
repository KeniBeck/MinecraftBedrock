"""Almacén durable del buffer de consola sobre Postgres (Fase A paso 2).

Implementa ``ConsoleLogWriter`` (lectura del puerto de dominio + ``append``).
La línea caliente sigue siendo el anillo en memoria (``ConsoleLog`` por
servidor) para no cambiar la semántica del streaming; ``append`` persiste cada
línea con su ``seq`` y **recorta** periódicamente las filas más antiguas al
límite de retención (salida de consola = telemetría transitoria, no auditoría).
Al reiniciar el proceso, ``get`` rehidrata el anillo desde la cola persistida
con ``seq`` continuos (``ConsoleLog.from_records``).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.console.domain.console_log import ConsoleLine, ConsoleLog
from app.modules.console.infrastructure.models import ConsoleLineRow


class PostgresConsoleLogStore:
    """Buffer por servidor con persistencia en ``console_lines``."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        max_lines: int = 1000,
        prune_every: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._max_lines = max_lines
        self._prune_every = prune_every or max(100, max_lines)
        self._rings: dict[str, ConsoleLog] = {}
        self._inserted: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def get(self, server_id: str) -> ConsoleLog:
        """Devuelve el buffer del servidor, rehidratándolo si no está en caché."""
        async with self._lock:
            log = self._rings.get(server_id)
            if log is None:
                log = await self._hydrate(server_id)
                self._rings[server_id] = log
            return log

    async def append(self, server_id: str, line: str) -> ConsoleLine:
        """Añade la línea al anillo y la persiste con su ``seq``."""
        log = await self.get(server_id)
        record = log.append(line)
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            session.add(
                ConsoleLineRow(
                    server_id=server_id,
                    seq=record.seq,
                    line=record.line,
                    created_at=now,
                )
            )
            await session.commit()

        inserted = self._inserted.get(server_id, 0) + 1
        self._inserted[server_id] = inserted
        if inserted >= self._prune_every:
            await self._prune(server_id)
            self._inserted[server_id] = 0
        return record

    async def _hydrate(self, server_id: str) -> ConsoleLog:
        """Reconstruye el anillo desde la cola persistida (últimas ``max_lines``)."""
        stmt = (
            select(ConsoleLineRow)
            .where(ConsoleLineRow.server_id == server_id)
            .order_by(ConsoleLineRow.seq.desc())
            .limit(self._max_lines)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        records = [ConsoleLine(seq=row.seq, server_id=server_id, line=row.line) for row in rows]
        return ConsoleLog.from_records(server_id, records, max_lines=self._max_lines)

    async def _prune(self, server_id: str) -> None:
        """Recorta a las últimas ``max_lines`` filas del servidor."""
        keep = (
            select(ConsoleLineRow.seq)
            .where(ConsoleLineRow.server_id == server_id)
            .order_by(ConsoleLineRow.seq.desc())
            .limit(self._max_lines)
        )
        stmt = delete(ConsoleLineRow).where(
            ConsoleLineRow.server_id == server_id,
            ConsoleLineRow.seq.not_in(keep),
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()
