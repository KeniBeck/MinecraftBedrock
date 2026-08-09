"""Routers HTTP del módulo Server (vertical slice §16 ``modules/server/api``).

REST sobre la facade Server: ciclo de vida, config y versión. Cada operación
se protege con ``require_server_action`` (ACL por servidor: operador+ para
escritura, viewer para consultas). La API solo traduce request → comando y
resultado → respuesta (Blueprint §4.7); no contiene reglas de negocio.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.bootstrap.container import Container
from app.bootstrap.errors import http_error
from app.bootstrap.security import (
    get_container,
    get_current_user,
    require_action,
    require_server_action,
)
from app.kernel.ports.access import Identity
from app.modules.server.api.schemas import (
    ApplyConfigRequest,
    ChangeVersionRequest,
    CreateServerRequest,
    RestartServerRequest,
    ServerConnectionResponse,
    ServerDetailResourcesResponse,
    ServerDetailResponse,
    ServerResponse,
    StopServerRequest,
    UpdateResourcesRequest,
)
from app.modules.server.application.commands import (
    ApplyConfigCommand,
    ChangeVersionCommand,
    CreateServerCommand,
    RemoveServerCommand,
    RestartServerCommand,
    StartServerCommand,
    StopServerCommand,
    UpdateResourcesCommand,
)
from app.modules.server.application.facade import ServerFacade
from app.modules.server.application.results import ServerView
from app.modules.server.domain.server import ServerId

router = APIRouter(tags=["server"])


def _facade(request: Request) -> ServerFacade:
    return get_container(request).server_facade


async def _resources(container: Container, server_id: str) -> ServerDetailResourcesResponse:
    """Recursos del servidor desde el ``RuntimeSpec`` persistido + ajustes de disco.

    CPU/RAM se leen del ``jsonb`` ``spec["resources"]`` (sin columnas nuevas);
    ``disk_gb`` sale del ajuste global ``limits.default_disk_gb``.
    """
    resources: dict[str, Any] = {}
    server = await container.server_repository.get(ServerId(server_id))
    if server is not None:
        resources = server.spec.resources
    cpu_cores = float(resources.get("cpus", resources.get("cpu_cores", 0)))
    ram_mb = int(resources.get("memory_mb", resources.get("ram_mb", 0)))
    disk_gb = int(container.settings_service.get("limits.default_disk_gb", 10))
    return ServerDetailResourcesResponse(cpu_cores=cpu_cores, ram_mb=ram_mb, disk_gb=disk_gb)


def _response(view: ServerView) -> ServerResponse:
    conn = view.connection
    return ServerResponse(
        id=view.id,
        name=view.name,
        state=view.state.value,
        version=view.version,
        image_ref=view.image_ref,
        runtime_id=view.runtime_id,
        created_at=view.created_at,
        updated_at=view.updated_at,
        connection=ServerConnectionResponse(
            host=conn.host,
            port=conn.port,
            port_v6=conn.port_v6,
            rcon_port=conn.rcon_port,
            address=conn.address,
        ),
    )


@router.get(
    "/servers",
    response_model=list[ServerResponse],
    summary="Listar servidores visibles",
)
async def list_servers(
    request: Request,
    identity: Identity = Depends(get_current_user),
) -> list[ServerResponse]:
    views = await _facade(request).list_servers()
    visible: list[ServerResponse] = []
    for view in views:
        decision = await get_container(request).iam_facade.access_control.authorize(
            identity, "server.view", view.id
        )
        if decision.allowed:
            visible.append(_response(view))
    return visible


@router.get(
    "/servers/{server_id}",
    response_model=ServerDetailResponse,
    summary="Estado de un servidor",
)
async def get_server(
    server_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("server.view")),
) -> ServerDetailResponse:
    del identity
    view = await _facade(request).get_server(server_id)
    if view is None:
        raise http_error(404, "SERVER.NOT_FOUND", f"Servidor no encontrado: {server_id}")
    container = get_container(request)
    base = _response(view)
    return ServerDetailResponse(
        **base.model_dump(),
        resources=await _resources(container, server_id),
    )


@router.post(
    "/servers",
    response_model=ServerResponse,
    status_code=201,
    summary="Crear servidor (admin)",
)
async def create_server(
    body: CreateServerRequest,
    request: Request,
    identity: Identity = Depends(require_action("server.create")),
) -> ServerResponse:
    view = await _facade(request).create(
        CreateServerCommand(
            name=body.name,
            version=body.version,
            template_id=body.template_id,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.post(
    "/servers/{server_id}/start",
    response_model=ServerResponse,
    summary="Iniciar servidor",
)
async def start_server(
    server_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("server.start")),
) -> ServerResponse:
    view = await _facade(request).start(
        StartServerCommand(server_id=server_id, actor_id=identity.id)
    )
    return _response(view)


@router.post(
    "/servers/{server_id}/stop",
    response_model=ServerResponse,
    summary="Detener servidor",
)
async def stop_server(
    server_id: str,
    request: Request,
    body: StopServerRequest,
    identity: Identity = Depends(require_server_action("server.stop")),
) -> ServerResponse:
    view = await _facade(request).stop(
        StopServerCommand(server_id=server_id, grace=body.grace, actor_id=identity.id)
    )
    return _response(view)


@router.post(
    "/servers/{server_id}/restart",
    response_model=ServerResponse,
    summary="Reiniciar servidor",
)
async def restart_server(
    server_id: str,
    request: Request,
    body: RestartServerRequest,
    identity: Identity = Depends(require_server_action("server.restart")),
) -> ServerResponse:
    view = await _facade(request).restart(
        RestartServerCommand(server_id=server_id, grace=body.grace, actor_id=identity.id)
    )
    return _response(view)


@router.delete("/servers/{server_id}", status_code=204, summary="Eliminar servidor")
async def remove_server(
    server_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("server.delete")),
) -> None:
    await _facade(request).remove(RemoveServerCommand(server_id=server_id, actor_id=identity.id))


@router.post(
    "/servers/{server_id}/config",
    response_model=ServerResponse,
    summary="Aplicar config deseada",
)
async def apply_config(
    server_id: str,
    request: Request,
    body: ApplyConfigRequest,
    identity: Identity = Depends(require_server_action("server.config.apply")),
) -> ServerResponse:
    view = await _facade(request).apply_config(
        ApplyConfigCommand(
            server_id=server_id,
            config_rev=body.config_rev,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.post(
    "/servers/{server_id}/version",
    response_model=ServerResponse,
    summary="Cambiar versión",
)
async def change_version(
    server_id: str,
    request: Request,
    body: ChangeVersionRequest,
    identity: Identity = Depends(require_server_action("server.version.change")),
) -> ServerResponse:
    view = await _facade(request).change_version(
        ChangeVersionCommand(
            server_id=server_id,
            version=body.version,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.put(
    "/servers/{server_id}/resources",
    response_model=ServerResponse,
    summary="Actualizar CPU/RAM de un servidor",
)
async def update_resources(
    server_id: str,
    request: Request,
    body: UpdateResourcesRequest,
    identity: Identity = Depends(require_server_action("server.update")),
) -> ServerResponse:
    view = await _facade(request).update_resources(
        UpdateResourcesCommand(
            server_id=server_id,
            cpu_cores=body.cpu_cores,
            ram_mb=body.ram_mb,
            actor_id=identity.id,
        )
    )
    return _response(view)
