"""Repositorio durable de Scheduler sobre Postgres (Fase G paso 15).

Implementa ``SchedulerTaskRepositoryPort`` sin tocar el contrato de dominio:
una sesión por operación; ``save_task`` hace upsert (la entidad es la autoridad
del estado). ``list_due`` selecciona tareas activas vencidas ordenadas por
próxima ejecución.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.scheduler.domain.task import ScheduleTask, ScheduleTaskState
from app.modules.scheduler.infrastructure.models import SchedulerTaskRow
from app.modules.scheduler.infrastructure.serialization import task_from_row, task_to_row


class PostgresSchedulerTaskRepository:
    """Persistencia de tareas programadas en ``scheduler_tasks``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_task(self, task: ScheduleTask) -> None:
        values = task_to_row(task)
        stmt = pg_insert(SchedulerTaskRow).values(**values)
        update_map = {key: getattr(stmt.excluded, key) for key in values}
        stmt = stmt.on_conflict_do_update(index_elements=[SchedulerTaskRow.id], set_=update_map)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_task(self, task_id: str) -> ScheduleTask | None:
        stmt = select(SchedulerTaskRow).where(SchedulerTaskRow.id == task_id)
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return task_from_row(row) if row is not None else None

    async def list_tasks(self, server_id: str) -> list[ScheduleTask]:
        stmt = select(SchedulerTaskRow).where(SchedulerTaskRow.server_id == server_id)
        stmt = stmt.order_by(SchedulerTaskRow.created_at)
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [task_from_row(row) for row in rows]

    async def delete_task(self, task_id: str) -> None:
        from sqlalchemy import delete

        stmt = delete(SchedulerTaskRow).where(SchedulerTaskRow.id == task_id)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def list_due(self, now: datetime) -> list[ScheduleTask]:
        stmt = select(SchedulerTaskRow).where(
            SchedulerTaskRow.state == ScheduleTaskState.ACTIVE.value,
            SchedulerTaskRow.next_run_at.is_not(None),
            SchedulerTaskRow.next_run_at <= now,
        )
        stmt = stmt.order_by(SchedulerTaskRow.next_run_at)
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [task_from_row(row) for row in rows]
