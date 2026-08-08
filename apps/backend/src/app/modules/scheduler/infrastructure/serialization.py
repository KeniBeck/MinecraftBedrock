"""Serialización del dominio Scheduler ↔ filas (test sin BBDD)."""

from __future__ import annotations

from typing import Any

from app.modules.scheduler.domain.task import ScheduleTask, ScheduleTaskState, ScheduleTaskType
from app.modules.scheduler.infrastructure.models import SchedulerTaskRow


def task_to_row(task: ScheduleTask) -> dict[str, Any]:
    """Proyección de ``ScheduleTask`` a los campos de ``SchedulerTaskRow``."""
    return {
        "id": task.id,
        "server_id": task.server_id,
        "name": task.name,
        "type": task.type.value,
        "cron": task.cron,
        "payload": task.payload,
        "state": task.state.value,
        "next_run_at": task.next_run_at,
        "last_run_at": task.last_run_at,
        "last_result": task.last_result,
        "failures": task.failures,
        "max_retries": task.max_retries,
        "backoff_seconds": task.backoff_seconds,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def task_from_row(row: SchedulerTaskRow) -> ScheduleTask:
    """Reconstruye ``ScheduleTask`` desde una fila."""
    return ScheduleTask(
        id=row.id,
        server_id=row.server_id,
        name=row.name,
        type=ScheduleTaskType(row.type),
        cron=row.cron,
        payload=dict(row.payload or {}),
        state=ScheduleTaskState(row.state),
        next_run_at=row.next_run_at,
        last_run_at=row.last_run_at,
        last_result=row.last_result,
        failures=row.failures,
        max_retries=row.max_retries,
        backoff_seconds=row.backoff_seconds,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
