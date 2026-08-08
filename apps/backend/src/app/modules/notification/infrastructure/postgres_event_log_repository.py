"""Repositorio durable del ``EventLog`` sobre Postgres (Fase H §16.13).

Implementa ``EventLogRepositoryPort``: ``next_seq`` consume una secuencia
Postgres (``noti_event_log_seq``), ``append`` inserta la entrada numerada y
``get_events_since`` consulta por canal y rango de ``seq`` en orden. Es
append-only: no hay update/delete.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.notification.domain.repository import EventLogEntry
from app.modules.notification.infrastructure.models import NotificationLogRow

_SEQ_NAME = "noti_event_log_seq"


class PostgresEventLogRepository:
    """Persistencia del ``EventLog`` en ``noti_event_log``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def next_seq(self) -> int:
        stmt = select(sa.func.nextval(_SEQ_NAME))
        async with self._session_factory() as session:
            value = (await session.execute(stmt)).scalar_one()
        return int(value)

    async def append(self, entry: EventLogEntry) -> None:
        stmt = pg_insert(NotificationLogRow).values(
            id=str(entry.seq),  # id derivado y único del seq para simplificar
            seq=entry.seq,
            event_type=entry.event_type,
            scope=entry.scope,
            server_id=entry.server_id,
            user_id=entry.user_id,
            payload=dict(entry.payload),
            created_at=entry.created_at,
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_events_since(
        self,
        last_seq: int,
        *,
        scope: str | None = None,
        server_id: str | None = None,
        user_id: str | None = None,
        limit: int = 1000,
    ) -> list[EventLogEntry]:
        stmt = select(NotificationLogRow).where(NotificationLogRow.seq > last_seq)
        if scope is not None:
            stmt = stmt.where(NotificationLogRow.scope == scope)
        if server_id is not None:
            stmt = stmt.where(NotificationLogRow.server_id == server_id)
        if user_id is not None:
            stmt = stmt.where(NotificationLogRow.user_id == user_id)
        stmt = stmt.order_by(NotificationLogRow.seq).limit(limit)
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [entry_from_row(row) for row in rows]

    async def latest_seq(self) -> int:
        stmt = select(sa.func.max(NotificationLogRow.seq))
        async with self._session_factory() as session:
            value = (await session.execute(stmt)).scalar_one()
        return int(value or 0)


def entry_from_row(row: NotificationLogRow) -> EventLogEntry:
    """Reconstruye la entrada de dominio desde la fila."""
    return EventLogEntry(
        seq=row.seq,
        event_type=row.event_type,
        scope=row.scope,
        server_id=row.server_id,
        user_id=row.user_id,
        payload=dict(row.payload or {}),
        created_at=row.created_at,
    )
