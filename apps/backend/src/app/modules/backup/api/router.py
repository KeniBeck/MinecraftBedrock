"""Routers HTTP del módulo Backup (vertical slice §16 ``modules/backup/api``).

REST sobre la facade Backup: crear, listar (por servidor/mundo), restaurar,
validar, descargar (streaming del artefacto), eliminar y prune. Los endpoints
son scoped a un servidor para reusar ``require_server_action`` (ACL por
servidor): las consultas/descarga son lectura (viewer+), el resto es
escritura (operator+, decisión del paso de cierre: las destructivas —
restaurar/eliminar — no exigen más que operator, consistente con
``server.delete``). El artefacto se descarga como ``StreamingResponse`` sin
cargarlo en memoria.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import BinaryIO

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.bootstrap.errors import http_error
from app.bootstrap.security import get_container, require_server_action
from app.kernel.errors import HttpError
from app.kernel.ports.access import Identity
from app.modules.backup.api.schemas import (
    BackupResponse,
    CreateBackupRequest,
    PruneBackupRequest,
)
from app.modules.backup.application.commands import (
    CreateBackupCommand,
    DeleteBackupCommand,
    PruneBackupCommand,
    RestoreBackupCommand,
    ValidateBackupCommand,
)
from app.modules.backup.application.facade import BackupFacade
from app.modules.backup.application.results import BackupView

router = APIRouter(tags=["backup"])


def _facade(request: Request) -> BackupFacade:
    return get_container(request).backup_facade


def _response(view: BackupView) -> BackupResponse:
    return BackupResponse(
        id=view.id,
        server_id=view.server_id,
        world_name=view.world_name,
        state=view.state,
        size_bytes=view.size_bytes,
        checksum=view.checksum,
        entries=list(view.entries),
        duration_seconds=view.duration_seconds,
        protected=view.protected,
        orphaned=view.orphaned,
        error=view.error,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def _not_found(server_id: str, backup_id: str) -> HttpError:
    return http_error(
        404,
        "BACKUP.NOT_FOUND",
        "El backup no existe en este servidor",
        {"server_id": server_id, "backup_id": backup_id},
    )


async def _require_backup(
    request: Request,
    server_id: str,
    backup_id: str,
) -> BackupView:
    """Resuelve un backup del servidor, ocultando existencia si no coincide."""
    view = await _facade(request).get_backup(backup_id)
    if view is None or view.server_id != server_id:
        raise _not_found(server_id, backup_id)
    return view


@router.post(
    "/servers/{server_id}/backups",
    response_model=BackupResponse,
    status_code=201,
    summary="Crear un backup de un mundo",
)
async def create_backup(
    server_id: str,
    body: CreateBackupRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("backup.create")),
) -> BackupResponse:
    view = await _facade(request).create_backup(
        CreateBackupCommand(
            server_id=server_id,
            world_name=body.world_name,
            protected=body.protected,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.get(
    "/servers/{server_id}/backups",
    response_model=list[BackupResponse],
    summary="Listar backups del servidor",
)
async def list_backups(
    server_id: str,
    request: Request,
    world_name: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    identity: Identity = Depends(require_server_action("backup.list")),
) -> list[BackupResponse]:
    del identity
    views = await _facade(request).list_backups(
        server_id,
        world_name=world_name,
        limit=limit,
    )
    return [_response(view) for view in views]


@router.get(
    "/servers/{server_id}/backups/{backup_id}",
    response_model=BackupResponse,
    summary="Detalle de un backup",
)
async def get_backup(
    server_id: str,
    backup_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("backup.view")),
) -> BackupResponse:
    del identity
    return _response(await _require_backup(request, server_id, backup_id))


@router.post(
    "/servers/{server_id}/backups/{backup_id}/restore",
    response_model=BackupResponse,
    summary="Restaurar un backup sobre su mundo",
)
async def restore_backup(
    server_id: str,
    backup_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("backup.restore")),
) -> BackupResponse:
    await _require_backup(request, server_id, backup_id)
    view = await _facade(request).restore_backup(
        RestoreBackupCommand(backup_id=backup_id, actor_id=identity.id)
    )
    return _response(view)


@router.post(
    "/servers/{server_id}/backups/{backup_id}/validate",
    response_model=BackupResponse,
    summary="Validar la integridad del artefacto",
)
async def validate_backup(
    server_id: str,
    backup_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("backup.validate")),
) -> BackupResponse:
    await _require_backup(request, server_id, backup_id)
    view = await _facade(request).validate(
        ValidateBackupCommand(backup_id=backup_id, actor_id=identity.id)
    )
    return _response(view)


@router.get(
    "/servers/{server_id}/backups/{backup_id}/download",
    summary="Descargar el artefacto de un backup (tar.zst)",
)
async def download_backup(
    server_id: str,
    backup_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("backup.download")),
) -> StreamingResponse:
    del identity
    view = await _require_backup(request, server_id, backup_id)
    download = await _facade(request).download(backup_id)
    assert download is not None
    return StreamingResponse(
        _iter_stream(download.stream),
        media_type="application/zstd",
        headers={
            "Content-Disposition": (f'attachment; filename="{view.world_name}-{view.id}.tar.zst"')
        },
    )


@router.delete(
    "/servers/{server_id}/backups/{backup_id}",
    status_code=204,
    summary="Eliminar un backup (no los protegidos)",
)
async def delete_backup(
    server_id: str,
    backup_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("backup.delete")),
) -> None:
    await _require_backup(request, server_id, backup_id)
    await _facade(request).delete_backup(
        DeleteBackupCommand(backup_id=backup_id, actor_id=identity.id)
    )


@router.post(
    "/servers/{server_id}/backups/prune",
    response_model=list[BackupResponse],
    summary="Aplicar retención keep-last-N por mundo",
)
async def prune_backups(
    server_id: str,
    body: PruneBackupRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("backup.prune")),
) -> list[BackupResponse]:
    views = await _facade(request).prune(
        PruneBackupCommand(
            server_id=server_id,
            keep_last_n=body.keep_last_n,
            actor_id=identity.id,
        )
    )
    return [_response(view) for view in views]


def _iter_stream(stream: BinaryIO, chunk_size: int = 1 << 20) -> Iterator[bytes]:
    try:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        stream.close()
