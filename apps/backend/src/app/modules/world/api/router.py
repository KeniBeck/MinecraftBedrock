"""Routers HTTP del módulo World (vertical slice §16 ``modules/world/api``).

REST sobre la facade World: crear, importar (multipart con límite de tamaño),
exportar (streaming del snapshot), duplicar, eliminar, activar, listar y
sync. Cada operación se protege con ``require_server_action`` (ACL por
servidor: viewer para consultas/export, operator+ para escrituras). La API
solo traduce request → comando y resultado → respuesta (Blueprint §4.7); el
límite del multipart se valida aquí porque Starlette solo lo aplica a campos
(``MultiPartParser.max_part_size``), no a los archivos que spolea a disco.

El snapshot exportado se sirve como ``StreamingResponse`` sin cargar el mundo
en memoria; ``consistent`` (decisión del paso de cierre: si ``save hold`` se
confirmó o el servidor estaba detenido) viaja en la cabecera
``X-BedrockPanel-Consistent`` porque el cuerpo es el artefacto binario.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import BinaryIO

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.bootstrap.errors import http_error
from app.bootstrap.security import get_container, require_server_action
from app.kernel.ports.access import Identity
from app.modules.world.api.schemas import (
    CreateWorldRequest,
    DuplicateWorldRequest,
    UpdateWorldRequest,
    WorldResponse,
)
from app.modules.world.application.commands import (
    ActivateWorldCommand,
    CreateWorldCommand,
    DeleteWorldCommand,
    DuplicateWorldCommand,
    ExportWorldCommand,
    ImportWorldCommand,
    UpdateWorldCommand,
)
from app.modules.world.application.facade import WorldFacade
from app.modules.world.application.results import ExportWorldResult, WorldView

router = APIRouter(tags=["world"])


def _facade(request: Request) -> WorldFacade:
    return get_container(request).world_facade


def _response(view: WorldView) -> WorldResponse:
    return WorldResponse(
        id=view.id,
        server_id=view.server_id,
        name=view.name,
        level_name=view.level_name,
        size_bytes=view.size_bytes,
        activated=view.activated,
        created_at=view.created_at,
        updated_at=view.updated_at,
        seed=view.seed,
        gamemode=view.gamemode,
        difficulty=view.difficulty,
        view_distance=view.view_distance,
    )


@router.get(
    "/servers/{server_id}/worlds",
    response_model=list[WorldResponse],
    summary="Listar mundos de un servidor",
)
async def list_worlds(
    server_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("world.list")),
) -> list[WorldResponse]:
    del identity
    views = await _facade(request).list_worlds(server_id)
    return [_response(view) for view in views]


@router.post(
    "/servers/{server_id}/worlds",
    response_model=WorldResponse,
    status_code=201,
    summary="Crear un mundo nuevo",
)
async def create_world(
    server_id: str,
    body: CreateWorldRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("world.create")),
) -> WorldResponse:
    view = await _facade(request).create(
        CreateWorldCommand(
            server_id=server_id,
            name=body.name,
            seed=body.seed,
            gamemode=body.gamemode,
            difficulty=body.difficulty,
            view_distance=body.view_distance,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.post(
    "/servers/{server_id}/worlds/import",
    response_model=WorldResponse,
    status_code=201,
    summary="Importar un snapshot (.mcworld/tar.gz)",
)
async def import_world(
    server_id: str,
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    identity: Identity = Depends(require_server_action("world.import")),
) -> WorldResponse:
    stream = file.file
    stream.seek(0, os.SEEK_END)
    size_bytes = stream.tell()
    stream.seek(0)
    container = get_container(request)
    max_mb = container.settings_service.get_int("limits.max_world_size_mb", 2048)
    limit = max_mb * 1024 * 1024
    if size_bytes > limit:
        raise http_error(
            413,
            "WORLD.IMPORT_TOO_LARGE",
            "El snapshot supera el tamaño máximo permitido",
            {"server_id": server_id, "limit_bytes": limit, "size_bytes": size_bytes},
        )
    view = await _facade(request).import_world(
        ImportWorldCommand(
            server_id=server_id,
            name=name,
            stream=stream,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.post(
    "/servers/{server_id}/worlds/sync",
    response_model=list[WorldResponse],
    status_code=201,
    summary="Reconciliar metadata con el storage",
)
async def sync_worlds(
    server_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("world.sync")),
) -> list[WorldResponse]:
    del identity
    views = await _facade(request).sync(server_id)
    return [_response(view) for view in views]


@router.get(
    "/servers/{server_id}/worlds/{name}/export",
    summary="Exportar un mundo (snapshot .mcworld)",
)
async def export_world(
    server_id: str,
    name: str,
    request: Request,
    identity: Identity = Depends(require_server_action("world.export")),
) -> StreamingResponse:
    result = await _facade(request).export_world(
        ExportWorldCommand(server_id=server_id, name=name, actor_id=identity.id)
    )
    return _export_response(result)


@router.patch(
    "/servers/{server_id}/worlds/{name}",
    response_model=WorldResponse,
    summary="Renombrar y/o ajustar un mundo",
)
async def update_world(
    server_id: str,
    name: str,
    body: UpdateWorldRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("world.update")),
) -> WorldResponse:
    view = await _facade(request).update(
        UpdateWorldCommand(
            server_id=server_id,
            name=name,
            new_name=body.name,
            seed=body.seed,
            gamemode=body.gamemode,
            difficulty=body.difficulty,
            view_distance=body.view_distance,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.post(
    "/servers/{server_id}/worlds/{name}/duplicate",
    response_model=WorldResponse,
    status_code=201,
    summary="Duplicar un mundo",
)
async def duplicate_world(
    server_id: str,
    name: str,
    body: DuplicateWorldRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("world.duplicate")),
) -> WorldResponse:
    view = await _facade(request).duplicate(
        DuplicateWorldCommand(
            server_id=server_id,
            source=name,
            target=body.target,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.post(
    "/servers/{server_id}/worlds/{name}/activate",
    response_model=WorldResponse,
    summary="Activar un mundo (excluyente)",
)
async def activate_world(
    server_id: str,
    name: str,
    request: Request,
    identity: Identity = Depends(require_server_action("world.activate")),
) -> WorldResponse:
    view = await _facade(request).activate(
        ActivateWorldCommand(server_id=server_id, name=name, actor_id=identity.id)
    )
    return _response(view)


@router.delete(
    "/servers/{server_id}/worlds/{name}",
    status_code=204,
    summary="Eliminar un mundo",
)
async def delete_world(
    server_id: str,
    name: str,
    request: Request,
    identity: Identity = Depends(require_server_action("world.delete")),
) -> None:
    await _facade(request).delete(
        DeleteWorldCommand(server_id=server_id, name=name, actor_id=identity.id)
    )


def _export_response(result: ExportWorldResult) -> StreamingResponse:
    """Envuelve el snapshot como streaming, cerrando el stream al terminar."""
    return StreamingResponse(
        _iter_stream(result.stream),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{result.world.name}.mcworld"',
            "X-BedrockPanel-Consistent": "true" if result.consistent else "false",
        },
    )


def _iter_stream(stream: BinaryIO, chunk_size: int = 1 << 20) -> Iterator[bytes]:
    try:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        stream.close()
