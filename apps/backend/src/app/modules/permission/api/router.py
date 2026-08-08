"""Routers HTTP del módulo Permission (vertical slice §16).

Endpoints bajo ``/servers/{server_id}/permissions`` para gestionar
allowlist y niveles de permiso (operator/member/visitor).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.bootstrap.errors import http_error
from app.bootstrap.security import get_container, require_server_action
from app.kernel.ports.access import Identity
from app.modules.permission.api.schemas import (
    AllowlistAddRequest,
    AllowlistEntryResponse,
    PermissionEntryResponse,
    SetAllowlistEnabledRequest,
    SetPermissionRequest,
)
from app.modules.permission.application.facade import PermissionFacade
from app.modules.permission.domain.entities import AllowlistEntry, PermissionEntry, PermissionLevel

router = APIRouter(tags=["permission"])


def _facade(request: Request) -> PermissionFacade:
    return get_container(request).permission_facade


def _allowlist_response(entry: AllowlistEntry) -> AllowlistEntryResponse:
    return AllowlistEntryResponse(
        name=entry.name,
        xuid=entry.xuid,
        ignores_player_limit=entry.ignores_player_limit,
    )


def _permission_response(entry: PermissionEntry) -> PermissionEntryResponse:
    return PermissionEntryResponse(xuid=entry.xuid, level=entry.level.value)


# -- allowlist ----------------------------------------------------------------


@router.post(
    "/servers/{server_id}/permissions/allowlist",
    response_model=AllowlistEntryResponse,
    status_code=201,
    summary="Agregar entrada a la allowlist",
)
async def add_allowlist_entry(
    server_id: str,
    body: AllowlistAddRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("permission.write")),
) -> AllowlistEntryResponse:
    del identity
    entry = await _facade(request).add_to_allowlist(
        server_id, body.name, body.xuid, body.ignores_player_limit
    )
    return _allowlist_response(entry)


@router.delete(
    "/servers/{server_id}/permissions/allowlist/{xuid}",
    status_code=204,
    summary="Quitar entrada de la allowlist",
)
async def remove_allowlist_entry(
    server_id: str,
    xuid: str,
    request: Request,
    identity: Identity = Depends(require_server_action("permission.write")),
) -> None:
    del identity
    await _facade(request).remove_from_allowlist(server_id, xuid)


@router.get(
    "/servers/{server_id}/permissions/allowlist",
    response_model=list[AllowlistEntryResponse],
    summary="Listar allowlist",
)
async def list_allowlist(
    server_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("permission.read")),
) -> list[AllowlistEntryResponse]:
    del identity
    entries = await _facade(request).list_allowlist(server_id)
    return [_allowlist_response(e) for e in entries]


@router.put(
    "/servers/{server_id}/permissions/allowlist-enabled",
    status_code=204,
    summary="Activar/desactivar ALLOW_LIST (env) y recrear el contenedor",
)
async def set_allowlist_enabled(
    server_id: str,
    body: SetAllowlistEnabledRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("permission.write")),
) -> None:
    await _facade(request).set_allowlist_enabled(server_id, body.enabled, actor_id=identity.id)


# -- permissions / operators --------------------------------------------------


@router.put(
    "/servers/{server_id}/permissions/operators/{xuid}",
    response_model=PermissionEntryResponse,
    status_code=200,
    summary="Asignar nivel de permiso a un jugador",
)
async def set_permission(
    server_id: str,
    xuid: str,
    body: SetPermissionRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("permission.write")),
) -> PermissionEntryResponse:
    try:
        level = PermissionLevel(body.level)
    except ValueError:
        raise http_error(
            400,
            "PERMISSION.INVALID_LEVEL",
            f"Nivel inválido: {body.level}. Usar operator, member o visitor.",
            {"level": body.level},
        ) from None
    entry = await _facade(request).set_permission_level(
        server_id, xuid, level, actor_id=identity.id
    )
    return _permission_response(entry)


@router.delete(
    "/servers/{server_id}/permissions/operators/{xuid}",
    status_code=204,
    summary="Quitar permiso de un jugador",
)
async def remove_permission(
    server_id: str,
    xuid: str,
    request: Request,
    identity: Identity = Depends(require_server_action("permission.write")),
) -> None:
    await _facade(request).remove_permission(server_id, xuid, actor_id=identity.id)
