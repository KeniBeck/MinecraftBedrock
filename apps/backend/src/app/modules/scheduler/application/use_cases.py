"""Use cases del módulo Scheduler (Blueprint §3.9).

- ``create`` — registra una tarea recurrente (cron) y publica ``TASK.SCHEDULED``.
- ``update`` — edita campos, valida cron y publica ``TASK.CANCELLED`` si se
  desactiva (cambio de estado, no borrado).
- ``delete`` — elimina y publica ``TASK.CANCELLED``.
- ``SchedulerEngine`` — el "reloj": evalúa las tareas que tocan ejecutarse y
  las ejecuta (dispara por tipo: comando de consola, backup, restart). En un
  fallo la tarea se marca y se publica ``TASK.FAILED``; el retry con backoff lo
  aplica ``TaskFailedHandler`` (§"consume sus propios reintentos").
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from app.kernel.events.bus import EventBusPort
from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.settings import SettingsPort
from app.kernel.time import TimeProviderPort
from app.modules.backup.application.commands import CreateBackupCommand
from app.modules.scheduler.application.commands import (
    CreateTaskCommand,
    DeleteTaskCommand,
    UpdateTaskCommand,
)
from app.modules.scheduler.application.cron import next_after
from app.modules.scheduler.application.ports import BackupRunner, ServerRunner
from app.modules.scheduler.application.results import ScheduleTaskView, task_to_view
from app.modules.scheduler.domain.errors import (
    SchedulerValidationError,
    TaskNotFoundError,
    TaskStateError,
)
from app.modules.scheduler.domain.events import (
    TASK_CANCELLED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_SCHEDULED,
    TASK_STARTED,
    task_event,
)
from app.modules.scheduler.domain.repository import SchedulerTaskRepositoryPort
from app.modules.scheduler.domain.task import ScheduleTask, ScheduleTaskState, ScheduleTaskType
from app.modules.server.application.commands import RestartServerCommand

_ACTOR = "scheduler"


@dataclass(slots=True)
class SchedulerDeps:
    """Dependencias comunes de la aplicación Scheduler."""

    repository: SchedulerTaskRepositoryPort
    bus: EventBusPort
    ids: IdGeneratorPort
    time: TimeProviderPort
    settings: SettingsPort
    backup: BackupRunner
    server: ServerRunner


class CreateTaskUseCase:
    """Programa una tarea recurrente (cron) sobre un servidor (§3.9)."""

    def __init__(self, deps: SchedulerDeps) -> None:
        self._deps = deps

    async def create(self, cmd: CreateTaskCommand) -> ScheduleTaskView:
        now = self._deps.time.now()
        task_type = _parse_type(cmd.type)
        _validate_payload(task_type, cmd.payload)
        next_run = next_after(cmd.cron, now)
        task = ScheduleTask(
            id=self._deps.ids.new_id(),
            server_id=cmd.server_id,
            name=cmd.name.strip() or task_type.value,
            type=task_type,
            cron=cmd.cron,
            payload=dict(cmd.payload),
            state=ScheduleTaskState.ACTIVE,
            next_run_at=next_run,
            failures=0,
            max_retries=max(0, cmd.max_retries),
            backoff_seconds=max(0, cmd.backoff_seconds),
            created_at=now,
            updated_at=now,
        )
        await self._deps.repository.save_task(task)
        await self._deps.bus.publish(
            task_event(TASK_SCHEDULED, task.id, task.server_id, extra={"name": task.name})
        )
        return task_to_view(task)


class UpdateTaskUseCase:
    """Edita una tarea programada (los campos que vienen seteados)."""

    def __init__(self, deps: SchedulerDeps) -> None:
        self._deps = deps

    async def update(self, cmd: UpdateTaskCommand) -> ScheduleTaskView:
        task = await self._deps.repository.get_task(cmd.task_id)
        if task is None:
            raise TaskNotFoundError(
                "La tarea no existe",
                context={"task_id": cmd.task_id},
            )
        now = self._deps.time.now()
        updated = _apply_updates(task, cmd, now)
        if cmd.state == "disabled" and task.state is ScheduleTaskState.ACTIVE:
            await self._deps.bus.publish(
                task_event(TASK_CANCELLED, task.id, task.server_id, extra={"name": task.name})
            )
        await self._deps.repository.save_task(updated)
        return task_to_view(updated)


class DeleteTaskUseCase:
    """Elimina una tarea y publica ``TASK.CANCELLED``."""

    def __init__(self, deps: SchedulerDeps) -> None:
        self._deps = deps

    async def delete(self, cmd: DeleteTaskCommand) -> None:
        task = await self._deps.repository.get_task(cmd.task_id)
        if task is None:
            raise TaskNotFoundError(
                "La tarea no existe",
                context={"task_id": cmd.task_id},
            )
        await self._deps.repository.delete_task(task.id)
        await self._deps.bus.publish(
            task_event(TASK_CANCELLED, task.id, task.server_id, extra={"name": task.name})
        )


class SchedulerEngine:
    """El "reloj" del módulo: evalua qué tareas tocan y las ejecuta (§3.9).

    ``tick(now)`` procesa las tareas activas con ``next_run_at <= now``. Una
    ejecución exitosa reprograma la siguiente ocurrencia cron y publica
    ``TASK.COMPLETED``; un fallo publica ``TASK.FAILED`` y el retry con backoff
    (o el tope ``max_retries``) lo resuelve ``TaskFailedHandler``.
    """

    def __init__(self, deps: SchedulerDeps) -> None:
        self._deps = deps

    async def tick(self, now: datetime | None = None) -> list[str]:
        """Ejecuta las tareas vencidas y devuelve los ids procesados."""
        clock = now or self._deps.time.now()
        due = await self._deps.repository.list_due(clock)
        processed: list[str] = []
        for task in due:
            if task.state is not ScheduleTaskState.ACTIVE:
                continue
            final = await self._run(task, clock)
            processed.append(final.id)
        return processed

    async def run_now(self, task: ScheduleTask, now: datetime) -> ScheduleTask:
        """Ejecuta una tarea inmediatamente (manual, fuera de su cron)."""
        if task.state is ScheduleTaskState.DISABLED:
            raise TaskStateError(
                "No se puede ejecutar una tarea desactivada",
                context={"task_id": task.id},
            )
        return await self._run(task, now)

    async def _run(self, task: ScheduleTask, now: datetime) -> ScheduleTask:
        running = replace(task, state=ScheduleTaskState.RUNNING, updated_at=now)
        await self._deps.repository.save_task(running)

        try:
            await self._dispatch(task, now)
        except Exception as exc:  # noqa: BLE001 — se normaliza en TASK.FAILED
            failed = replace(
                task,
                state=ScheduleTaskState.ACTIVE,
                failures=task.failures + 1,
                last_run_at=now,
                last_result=str(exc),
                updated_at=now,
            )
            await self._deps.repository.save_task(failed)
            await self._deps.bus.publish(
                task_event(
                    TASK_FAILED,
                    task.id,
                    task.server_id,
                    extra={"error": str(exc), "attempt": failed.failures},
                )
            )
            return await self._require(task.id)

        next_run = next_after(task.cron, now)
        ok = replace(
            task,
            state=ScheduleTaskState.ACTIVE,
            failures=0,
            next_run_at=next_run,
            last_run_at=now,
            last_result="ok",
            updated_at=now,
        )
        await self._deps.repository.save_task(ok)
        await self._deps.bus.publish(
            task_event(
                TASK_COMPLETED,
                task.id,
                task.server_id,
                extra={"next_run": next_run.isoformat()},
            )
        )
        return ok

    async def _dispatch(self, task: ScheduleTask, now: datetime) -> None:
        """Dispara la tarea según su tipo (§3.9): comando, backup o restart."""
        del now
        if task.type is ScheduleTaskType.COMMAND:
            commands = _commands_for(task)
            if not commands:
                raise SchedulerValidationError(
                    "La tarea command no tiene comandos",
                    context={"task_id": task.id},
                )
            await self._deps.bus.publish(
                task_event(
                    TASK_STARTED,
                    task.id,
                    task.server_id,
                    extra={"commands": commands},
                )
            )
            return
        if task.type is ScheduleTaskType.BACKUP:
            world = task.payload.get("world_name", "")
            if not world:
                raise SchedulerValidationError(
                    "La tarea backup no especifica world_name",
                    context={"task_id": task.id},
                )
            await self._deps.backup.create_backup(
                CreateBackupCommand(
                    server_id=task.server_id,
                    world_name=str(world),
                    actor_id=_ACTOR,
                )
            )
            return
        grace = int(task.payload.get("grace", 30))
        await self._deps.server.restart(
            RestartServerCommand(server_id=task.server_id, grace=grace, actor_id=_ACTOR)
        )

    async def _require(self, task_id: str) -> ScheduleTask:
        task = await self._deps.repository.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(
                "La tarea desapareció durante la ejecución",
                context={"task_id": task_id},
            )
        return task


def _parse_type(value: str) -> ScheduleTaskType:
    try:
        return ScheduleTaskType(value)
    except ValueError:
        raise SchedulerValidationError(
            "Tipo de tarea desconocido",
            context={"type": value, "opciones": [item.value for item in ScheduleTaskType]},
        ) from None


def _validate_payload(task_type: ScheduleTaskType, payload: dict[str, Any]) -> None:
    if task_type is ScheduleTaskType.COMMAND and not _commands_from(payload):
        raise SchedulerValidationError(
            "Una tarea command requiere 'commands' (o 'command') en el payload",
            context={"payload": payload},
        )
    if task_type is ScheduleTaskType.BACKUP and not str(payload.get("world_name", "")).strip():
        raise SchedulerValidationError(
            "Una tarea backup requiere 'world_name' en el payload",
            context={"payload": payload},
        )


def _commands_from(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("commands", payload.get("command"))
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str) and item.strip()]
    return []


def _commands_for(task: ScheduleTask) -> list[str]:
    return _commands_from(task.payload)


def _apply_updates(task: ScheduleTask, cmd: UpdateTaskCommand, now: datetime) -> ScheduleTask:
    name = task.name if cmd.name is None else cmd.name.strip()
    cron = task.cron
    next_run = task.next_run_at
    payload = task.payload
    if cmd.cron is not None:
        cron = cmd.cron
        next_run = next_after(cron, now)
    if cmd.payload is not None:
        payload = dict(cmd.payload)
        _validate_payload(task.type, payload)

    state = task.state
    failures = task.failures
    if cmd.state is not None:
        try:
            state = ScheduleTaskState(cmd.state)
        except ValueError:
            raise SchedulerValidationError(
                "Estado de tarea desconocido",
                context={"state": cmd.state},
            ) from None
        if state is ScheduleTaskState.ACTIVE and task.state is ScheduleTaskState.FAILED:
            failures = 0
            if next_run is None:
                next_run = next_after(cron, now)
        if state is ScheduleTaskState.DISABLED:
            next_run = None

    max_retries = task.max_retries if cmd.max_retries is None else max(0, cmd.max_retries)
    backoff = task.backoff_seconds if cmd.backoff_seconds is None else max(0, cmd.backoff_seconds)

    return replace(
        task,
        name=name,
        cron=cron,
        payload=payload,
        state=state,
        next_run_at=next_run,
        failures=failures,
        max_retries=max_retries,
        backoff_seconds=backoff,
        updated_at=now,
    )
