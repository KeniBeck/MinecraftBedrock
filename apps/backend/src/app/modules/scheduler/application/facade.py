"""Facade pública del módulo Scheduler (Blueprint §3.9).

Los consumidores usan esta facade, nunca las entidades: CRUD de tareas
programadas, ejecución puntual (``run_now``), el reloj (``tick``) y la
suscripción de handlers de eventos.
"""

from __future__ import annotations

from datetime import datetime

from app.modules.backup.domain.events import BACKUP_FAILED_TOPIC
from app.modules.scheduler.application.commands import (
    CreateTaskCommand,
    DeleteTaskCommand,
    RunTaskCommand,
    UpdateTaskCommand,
)
from app.modules.scheduler.application.handlers import (
    ScheduledBackupFailedHandler,
    ServerCrashedHandler,
    TaskFailedHandler,
)
from app.modules.scheduler.application.results import ScheduleTaskView, task_to_view
from app.modules.scheduler.application.use_cases import (
    CreateTaskUseCase,
    DeleteTaskUseCase,
    SchedulerDeps,
    SchedulerEngine,
    UpdateTaskUseCase,
)
from app.modules.scheduler.domain.errors import TaskNotFoundError
from app.modules.scheduler.domain.events import TASK_FAILED_TOPIC
from app.modules.scheduler.domain.task import ScheduleTask
from app.modules.server.domain.events import SERVER_CRASHED


class SchedulerFacade:
    """Puerta de entrada única al módulo Scheduler."""

    def __init__(self, deps: SchedulerDeps) -> None:
        self.deps = deps
        self._create = CreateTaskUseCase(deps)
        self._update = UpdateTaskUseCase(deps)
        self._delete = DeleteTaskUseCase(deps)
        self._engine = SchedulerEngine(deps)

    async def create_task(self, cmd: CreateTaskCommand) -> ScheduleTaskView:
        return await self._create.create(cmd)

    async def update_task(self, cmd: UpdateTaskCommand) -> ScheduleTaskView:
        return await self._update.update(cmd)

    async def delete_task(self, cmd: DeleteTaskCommand) -> None:
        await self._delete.delete(cmd)

    async def run_task(self, cmd: RunTaskCommand) -> ScheduleTaskView:
        task = await self._require(cmd.task_id)
        final = await self._engine.run_now(task, self.deps.time.now())
        return task_to_view(final)

    async def list_tasks(self, server_id: str) -> list[ScheduleTaskView]:
        tasks = await self.deps.repository.list_tasks(server_id)
        return [task_to_view(task) for task in tasks]

    async def get_task(self, task_id: str) -> ScheduleTaskView | None:
        task = await self.deps.repository.get_task(task_id)
        if task is None:
            return None
        return task_to_view(task)

    async def tick(self, now: datetime | None = None) -> list[str]:
        """Evalúa y ejecuta las tareas vencidas (el "reloj"). Devuelve sus ids."""
        return await self._engine.tick(now)

    async def _require(self, task_id: str) -> ScheduleTask:
        task = await self.deps.repository.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(
                "La tarea no existe",
                context={"task_id": task_id},
            )
        return task

    def register_handlers(self) -> None:
        """Suscriptores del módulo sobre el bus (§3.9)."""
        self.deps.bus.subscribe(
            TASK_FAILED_TOPIC,
            TaskFailedHandler(self.deps.repository, self.deps.time),
        )
        self.deps.bus.subscribe(
            BACKUP_FAILED_TOPIC,
            ScheduledBackupFailedHandler(self.deps.repository, self.deps.time, self.deps.settings),
        )
        self.deps.bus.subscribe(
            SERVER_CRASHED.lower(),
            ServerCrashedHandler(self.deps.repository, self.deps.time, self.deps.settings),
        )
