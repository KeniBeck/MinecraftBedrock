"""Repositorio de Scheduler en memoria (tests y MVP sin BBDD)."""

from __future__ import annotations

from datetime import datetime

from app.modules.scheduler.domain.task import ScheduleTask, ScheduleTaskState


class InMemorySchedulerRepository:
    """``SchedulerTaskRepositoryPort`` en memoria."""

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduleTask] = {}
        self._count = 0

    async def save_task(self, task: ScheduleTask) -> None:
        if task.id not in self._tasks:
            self._count += 1
        self._tasks[task.id] = task

    async def get_task(self, task_id: str) -> ScheduleTask | None:
        return self._tasks.get(task_id)

    async def list_tasks(self, server_id: str) -> list[ScheduleTask]:
        return [task for task in self._tasks.values() if task.server_id == server_id]

    async def delete_task(self, task_id: str) -> None:
        if task_id in self._tasks:
            self._count -= 1
            del self._tasks[task_id]

    async def list_due(self, now: datetime) -> list[ScheduleTask]:
        due = [
            task
            for task in self._tasks.values()
            if task.state is ScheduleTaskState.ACTIVE
            and task.next_run_at is not None
            and task.next_run_at <= now
        ]
        due.sort(key=lambda task: task.next_run_at or now)
        return due
