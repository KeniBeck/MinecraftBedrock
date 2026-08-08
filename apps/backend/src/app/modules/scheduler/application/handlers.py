"""Handlers de eventos que Scheduler consume (Blueprint §3.9).

- ``TaskFailedHandler`` — ``TASK.FAILED``: reintento con backoff exponencial
  (tope ``max_retries``) tras un fallo. Es el único que decide el retry.
- ``ScheduledBackupFailedHandler`` — ``BACKUP.FAILED``: reconcilia la última
  ejecución de la tarea ``backup`` del servidor (no reintenta: la autoridad del
  retry es ``TaskFailedHandler``; evita doble conteo).
- ``ServerCrashedHandler`` — ``SERVER.CRASHED``: política de reinicio. Ni
  Monitoring ni Server reintentan un arranque tras crash (Server solo registra
  ``mark_crashed``); corresponde a Scheduler adelantar la próxima ejecución de
  una tarea ``restart`` con backoff de crash, no intentarlo de inmediato.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from app.kernel.events.event import DomainEvent
from app.kernel.ports.settings import SettingsPort
from app.kernel.time import TimeProviderPort
from app.modules.scheduler.domain.repository import SchedulerTaskRepositoryPort
from app.modules.scheduler.domain.task import ScheduleTaskState, ScheduleTaskType


class TaskFailedHandler:
    """``TASK.FAILED`` → reintento con backoff o tarea como ``FAILED`` (§3.9)."""

    def __init__(
        self,
        repository: SchedulerTaskRepositoryPort,
        time: TimeProviderPort,
    ) -> None:
        self._repository = repository
        self._time = time

    async def __call__(self, event: DomainEvent) -> None:
        task_id = _task_id_from(event)
        if task_id is None:
            return
        task = await self._repository.get_task(task_id)
        if task is None:
            return
        now = self._time.now()
        if task.max_retries and task.failures <= task.max_retries:
            delay = _retry_delay(task.backoff_seconds, task.failures)
            next_run = now + timedelta(seconds=delay)
            updated = replace(
                task, state=ScheduleTaskState.ACTIVE, next_run_at=next_run, updated_at=now
            )
        else:
            updated = replace(
                task,
                state=ScheduleTaskState.FAILED,
                next_run_at=None,
                updated_at=now,
            )
        await self._repository.save_task(updated)


class ScheduledBackupFailedHandler:
    """``BACKUP.FAILED`` → refleja el error en la tarea ``backup`` del servidor.

    Solo actualiza ``last_result`` si hay un tarea ``backup`` reciente (ventana
    configurable) para no mezclar el estado; el retry lo dispara el
    ``SchedulerEngine``/``TaskFailedHandler``.
    """

    def __init__(
        self,
        repository: SchedulerTaskRepositoryPort,
        time: TimeProviderPort,
        settings: SettingsPort,
    ) -> None:
        self._repository = repository
        self._time = time
        self._settings = settings

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id or event.payload.get("server_id")
        if not server_id:
            return
        error = str(event.payload.get("error", "BACKUP.FAILED"))
        now = self._time.now()
        window = float(self._settings.get("scheduler.reconcile_window_seconds", 30.0))
        for task in await self._repository.list_tasks(str(server_id)):
            if task.type is not ScheduleTaskType.BACKUP:
                continue
            if task.last_run_at is None or (now - task.last_run_at).total_seconds() > window:
                continue
            await self._repository.save_task(replace(task, last_result=error, updated_at=now))


class ServerCrashedHandler:
    """``SERVER.CRASHED`` → política de reinicio de Scheduler (§3.9).

    Adelanta la próxima ejecución de las tareas ``restart`` activas del servidor
    a ``ahora + crash_backoff``: reintenta el arranque con backoff, garantizando
    una separación mínima entre intentos tras un crash.
    """

    def __init__(
        self,
        repository: SchedulerTaskRepositoryPort,
        time: TimeProviderPort,
        settings: SettingsPort,
    ) -> None:
        self._repository = repository
        self._time = time
        self._settings = settings

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id or event.payload.get("server_id")
        if not server_id:
            return
        now = self._time.now()
        backoff = float(self._settings.get("scheduler.crash_retry_seconds", 60.0))
        for task in await self._repository.list_tasks(str(server_id)):
            if task.type is not ScheduleTaskType.RESTART:
                continue
            if task.state is not ScheduleTaskState.ACTIVE:
                continue
            await self._repository.save_task(
                replace(
                    task,
                    state=ScheduleTaskState.ACTIVE,
                    next_run_at=now + timedelta(seconds=backoff),
                    last_result="el servidor crasheó; arranque reprogramado",
                    updated_at=now,
                )
            )


def _task_id_from(event: DomainEvent) -> str | None:
    raw = event.payload.get("task_id")
    if not isinstance(raw, str):
        return None
    return raw if raw.strip() else None


def _retry_delay(backoff_seconds: int, attempt: int) -> int:
    return backoff_seconds * (1 << max(0, attempt - 1))
