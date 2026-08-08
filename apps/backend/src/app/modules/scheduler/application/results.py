"""Resultados de aplicación del módulo Scheduler (Blueprint §4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.scheduler.domain.task import ScheduleTask


@dataclass(frozen=True, slots=True)
class ScheduleTaskView:
    """DTO público de una tarea programada (sin detalles internos de ejecución)."""

    id: str
    server_id: str
    name: str
    type: str
    cron: str
    payload: dict[str, object]
    state: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_result: str | None
    failures: int
    max_retries: int
    backoff_seconds: int
    created_at: datetime | None
    updated_at: datetime | None


def task_to_view(task: ScheduleTask) -> ScheduleTaskView:
    return ScheduleTaskView(
        id=task.id,
        server_id=task.server_id,
        name=task.name,
        type=task.type.value,
        cron=task.cron,
        payload=dict(task.payload),
        state=task.state.value,
        next_run_at=task.next_run_at,
        last_run_at=task.last_run_at,
        last_result=task.last_result,
        failures=task.failures,
        max_retries=task.max_retries,
        backoff_seconds=task.backoff_seconds,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
