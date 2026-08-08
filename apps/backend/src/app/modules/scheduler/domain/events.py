"""Eventos de dominio ``TASK.*`` del módulo Scheduler (Blueprint §9.6).

Scheduler publica el ciclo de vida de una ejecución programada
(scheduled/started/completed/failed/cancelled) y consume ``TASK.FAILED`` (sus
propios reintentos con backoff), ``BACKUP.FAILED`` (fallo de una tarea de backup
programada) y ``SERVER.CRASHED`` (política de reinicio tras crash).

El contrato de ``TASK.STARTED`` para tareas de consola es
``{"server_id", "commands": [...]}``, que ya consume
``app.modules.console.application.handlers.TaskStartedHandler``.
"""

from __future__ import annotations

from typing import Any

from app.kernel.events.event import DomainEvent

TASK_SCHEDULED = "TASK.SCHEDULED"
TASK_STARTED = "TASK.STARTED"
TASK_COMPLETED = "TASK.COMPLETED"
TASK_FAILED = "TASK.FAILED"
TASK_CANCELLED = "TASK.CANCELLED"

TASK_SCHEDULED_TOPIC = "task.scheduled"
TASK_STARTED_TOPIC = "task.started"
TASK_COMPLETED_TOPIC = "task.completed"
TASK_FAILED_TOPIC = "task.failed"
TASK_CANCELLED_TOPIC = "task.cancelled"


def task_event(
    event_type: str,
    task_id: str,
    server_id: str,
    *,
    extra: dict[str, Any] | None = None,
) -> DomainEvent:
    """Construye un evento ``TASK.*`` normalizado (payload canónico)."""
    payload: dict[str, Any] = {"task_id": task_id, "server_id": server_id}
    if extra:
        payload.update(extra)
    return DomainEvent(type=event_type, event_id="", server_id=server_id, payload=payload)
