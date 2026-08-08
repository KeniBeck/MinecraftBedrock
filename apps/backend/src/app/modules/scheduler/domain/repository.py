"""Puerto de repositorio del módulo Scheduler (Blueprint §4.8)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.modules.scheduler.domain.task import ScheduleTask


class SchedulerTaskRepositoryPort(Protocol):
    """Persistencia de tareas programadas."""

    async def save_task(self, task: ScheduleTask) -> None:
        """Inserta o actualiza (upsert) una tarea."""

    async def get_task(self, task_id: str) -> ScheduleTask | None:
        """Devuelve una tarea por id, o ``None``."""

    async def list_tasks(self, server_id: str) -> list[ScheduleTask]:
        """Lista las tareas de un servidor."""

    async def delete_task(self, task_id: str) -> None:
        """Elimina una tarea."""

    async def list_due(self, now: datetime) -> list[ScheduleTask]:
        """Tareas activas con ``next_run_at <= now`` (ordenadas por próxima)."""
