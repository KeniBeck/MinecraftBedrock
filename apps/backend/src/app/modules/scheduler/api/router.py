"""Routers HTTP del módulo Scheduler (vertical slice §16 ``modules/scheduler/api``).

REST sobre la facade Scheduler: CRUD de tareas programadas (+ ``run`` para
ejecución puntual). Endpoints scoped a un servidor para reusar
``require_server_action`` (ACL por servidor): consultas = lectura (viewer+,
``scheduler.task.list``/``.view`` en ``READ_ACTIONS``); el resto = escritura
(operator+).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.bootstrap.errors import http_error
from app.bootstrap.security import get_container, require_server_action
from app.kernel.errors import HttpError
from app.kernel.ports.access import Identity
from app.modules.scheduler.api.schemas import (
    CreateTaskRequest,
    ScheduleTaskResponse,
    UpdateTaskRequest,
)
from app.modules.scheduler.application.commands import (
    CreateTaskCommand,
    DeleteTaskCommand,
    RunTaskCommand,
    UpdateTaskCommand,
)
from app.modules.scheduler.application.facade import SchedulerFacade
from app.modules.scheduler.application.results import ScheduleTaskView

router = APIRouter(tags=["scheduler"])


def _facade(request: Request) -> SchedulerFacade:
    return get_container(request).scheduler_facade


def _response(view: ScheduleTaskView) -> ScheduleTaskResponse:
    return ScheduleTaskResponse(
        id=view.id,
        server_id=view.server_id,
        name=view.name,
        type=view.type,
        cron=view.cron,
        payload=view.payload,
        state=view.state,
        next_run_at=view.next_run_at,
        last_run_at=view.last_run_at,
        last_result=view.last_result,
        failures=view.failures,
        max_retries=view.max_retries,
        backoff_seconds=view.backoff_seconds,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def _not_found(server_id: str, task_id: str) -> HttpError:
    return http_error(
        404,
        "TASK.NOT_FOUND",
        "La tarea no existe en este servidor",
        {"server_id": server_id, "task_id": task_id},
    )


async def _require_task(request: Request, server_id: str, task_id: str) -> ScheduleTaskView:
    """Resuelve una tarea del servidor, ocultando existencia si no coincide."""
    view = await _facade(request).get_task(task_id)
    if view is None or view.server_id != server_id:
        raise _not_found(server_id, task_id)
    return view


@router.post(
    "/servers/{server_id}/schedule/tasks",
    response_model=ScheduleTaskResponse,
    status_code=201,
    summary="Crear una tarea programada",
)
async def create_task(
    server_id: str,
    body: CreateTaskRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("scheduler.task.create")),
) -> ScheduleTaskResponse:
    view = await _facade(request).create_task(
        CreateTaskCommand(
            server_id=server_id,
            name=body.name,
            type=body.type,
            cron=body.cron,
            payload=body.payload,
            max_retries=body.max_retries,
            backoff_seconds=body.backoff_seconds,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.get(
    "/servers/{server_id}/schedule/tasks",
    response_model=list[ScheduleTaskResponse],
    summary="Listar tareas programadas del servidor",
)
async def list_tasks(
    server_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("task.list")),
) -> list[ScheduleTaskResponse]:
    del identity
    views = await _facade(request).list_tasks(server_id)
    return [_response(view) for view in views]


@router.get(
    "/servers/{server_id}/schedule/tasks/{task_id}",
    response_model=ScheduleTaskResponse,
    summary="Detalle de una tarea programada",
)
async def get_task(
    server_id: str,
    task_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("task.view")),
) -> ScheduleTaskResponse:
    del identity
    return _response(await _require_task(request, server_id, task_id))


@router.patch(
    "/servers/{server_id}/schedule/tasks/{task_id}",
    response_model=ScheduleTaskResponse,
    summary="Editar una tarea programada",
)
async def update_task(
    server_id: str,
    task_id: str,
    body: UpdateTaskRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("task.update")),
) -> ScheduleTaskResponse:
    await _require_task(request, server_id, task_id)
    view = await _facade(request).update_task(
        UpdateTaskCommand(
            task_id=task_id,
            name=body.name,
            cron=body.cron,
            payload=body.payload,
            max_retries=body.max_retries,
            backoff_seconds=body.backoff_seconds,
            state=body.state,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.post(
    "/servers/{server_id}/schedule/tasks/{task_id}/run",
    response_model=ScheduleTaskResponse,
    summary="Ejecutar una tarea ahora",
)
async def run_task(
    server_id: str,
    task_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("task.run")),
) -> ScheduleTaskResponse:
    del identity
    await _require_task(request, server_id, task_id)
    view = await _facade(request).run_task(RunTaskCommand(task_id=task_id))
    return _response(view)


@router.delete(
    "/servers/{server_id}/schedule/tasks/{task_id}",
    status_code=204,
    summary="Eliminar una tarea programada",
)
async def delete_task(
    server_id: str,
    task_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("task.delete")),
) -> None:
    del identity
    await _require_task(request, server_id, task_id)
    await _facade(request).delete_task(DeleteTaskCommand(task_id=task_id))
