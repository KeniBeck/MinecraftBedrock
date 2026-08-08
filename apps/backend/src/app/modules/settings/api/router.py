"""Routers HTTP del módulo Settings (vertical slice §16 ``modules/settings/api``).

Endpoints REST para administradores: leer todos / por categoría / por clave y
actualizar (PUT), múltiples (PATCH, atómico) o resetear (DELETE). Lectura exige
``settings.view``; escritura ``settings.update`` (ambas vía ``require_action``,
ámbito panel). La API no contiene reglas de negocio (Blueprint §4.7).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.bootstrap.security import get_container, require_action
from app.kernel.ports.access import Identity
from app.modules.settings.api.schemas import (
    PatchSettingsRequest,
    SettingResponse,
    SettingsListResponse,
    SettingValueRequest,
)
from app.modules.settings.application.service import SettingsService

router = APIRouter(tags=["settings"])


def _service(request: Request) -> SettingsService:
    return get_container(request).settings_service


@router.get(
    "/settings",
    response_model=SettingsListResponse,
    summary="Listar todos los settings (admin)",
)
async def list_settings(
    request: Request,
    identity: Identity = Depends(require_action("settings.view")),
) -> SettingsListResponse:
    del identity
    items = await _service(request).get_all()
    return SettingsListResponse(settings=[_to_response(item) for item in items])


@router.get(
    "/settings/category/{category}",
    response_model=SettingsListResponse,
    summary="Listar settings de una categoría (admin)",
)
async def list_category(
    category: str,
    request: Request,
    identity: Identity = Depends(require_action("settings.view")),
) -> SettingsListResponse:
    del identity
    items = await _service(request).get_category(category)
    return SettingsListResponse(settings=[_to_response(item) for item in items])


@router.get(
    "/settings/{key}",
    response_model=SettingResponse,
    summary="Leer un setting específico (admin)",
)
async def get_setting(
    key: str,
    request: Request,
    identity: Identity = Depends(require_action("settings.view")),
) -> SettingResponse:
    del identity
    items = await _service(request).get_all()
    match = next((item for item in items if item["key"] == key), None)
    if match is None:
        from app.modules.settings.domain.errors import SettingNotFoundError

        raise SettingNotFoundError(f"Ajuste desconocido: {key}")
    return _to_response(match)


@router.put(
    "/settings/{key}",
    response_model=SettingResponse,
    summary="Actualizar un setting (admin)",
)
async def update_setting(
    key: str,
    body: SettingValueRequest,
    request: Request,
    identity: Identity = Depends(require_action("settings.update")),
) -> SettingResponse:
    value = await _service(request).set(
        key,
        body.value,
        updated_by=identity.id,
        description=body.description,
    )
    return _to_response(
        {
            "key": key,
            "value": value,
            "category": "",
            "description": body.description,
        }
    )


@router.patch(
    "/settings",
    response_model=SettingsListResponse,
    summary="Actualizar múltiples settings (admin, atómico)",
)
async def patch_settings(
    body: PatchSettingsRequest,
    request: Request,
    identity: Identity = Depends(require_action("settings.update")),
) -> SettingsListResponse:
    await _service(request).set_many(body.values, updated_by=identity.id)
    items = await _service(request).get_all()
    updated_keys = set(body.values)
    return SettingsListResponse(
        settings=[_to_response(item) for item in items if item["key"] in updated_keys]
    )


@router.delete(
    "/settings/{key}",
    response_model=SettingResponse,
    summary="Resetear un setting a su valor por defecto (admin)",
)
async def reset_setting(
    key: str,
    request: Request,
    identity: Identity = Depends(require_action("settings.update")),
) -> SettingResponse:
    default = await _service(request).reset(key, updated_by=identity.id)
    return _to_response(
        {"key": key, "value": default, "category": "", "description": "reset a default"}
    )


def _to_response(item: dict[str, object]) -> SettingResponse:
    raw_description: object = item.get("description")
    description = raw_description if isinstance(raw_description, str) else None
    return SettingResponse(
        key=str(item["key"]),
        value=item["value"],
        category=str(item.get("category", "")),
        description=description,
        type=str(item.get("type", "any")),
        default=item.get("default"),
    )
