"""Routers HTTP del módulo Configuration (vertical slice §16 ``modules/configuration/api``).

REST sobre la facade Configuration: leer el perfil de config deseado (properties
de ``server.properties``, versión y revisión) y actualizarlo. La API solo
traduce request → operación de facade y resultado → respuesta (Blueprint §4.7).

La actualización valida → persiste → publica ``CONFIG.CHANGED``; Server consume
ese evento y recrea el contenedor con la config (aplicación unidireccional
§3.2/§3.7). Por tanto el puerto ``PUT`` **no recrea de forma síncrona**: la
recreación ocurre en segundo plano vía el bus de eventos en proceso.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request

from app.bootstrap.security import get_container, require_server_action
from app.kernel.errors import ValidationError
from app.kernel.ports.access import Identity
from app.modules.configuration.api.schemas import ConfigProfileResponse, UpdateConfigRequest
from app.modules.configuration.application.facade import ConfigurationFacade
from app.modules.configuration.domain.config_profile import ConfigProfile

router = APIRouter(tags=["configuration"])


def _facade(request: Request) -> ConfigurationFacade:
    return get_container(request).configuration_facade


def _default_version(request: Request) -> str:
    settings = get_container(request).settings_service
    return str(settings.get("defaults.version", settings.get("server.default_version", "LATEST")))


def _response(profile: ConfigProfile) -> ConfigProfileResponse:
    return ConfigProfileResponse(
        server_id=profile.server_id,
        version=profile.version,
        config_rev=profile.config_rev,
        properties=dict(profile.properties),
        applied=dict(profile.applied) if profile.applied is not None else None,
        applied_at=profile.applied_at,
        updated_at=profile.updated_at,
    )


@router.get(
    "/servers/{server_id}/configuration",
    response_model=ConfigProfileResponse,
    summary="Perfil de configuración actual (server.properties)",
)
async def get_configuration(
    server_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("server.config.read")),
) -> ConfigProfileResponse:
    del identity
    profile = await _facade(request).get_profile(server_id)
    if profile is None:
        # Servidor recién creado sin perfil: se devuelve un perfil vacío con la
        # versión por defecto (el frontend parte de los defaults del catálogo).
        return ConfigProfileResponse(
            server_id=server_id,
            version=_default_version(request),
            config_rev=0,
            properties={},
            applied=None,
            applied_at=None,
            updated_at=datetime.now(UTC),
        )
    return _response(profile)


@router.put(
    "/servers/{server_id}/configuration",
    response_model=ConfigProfileResponse,
    summary="Actualizar config deseada (server.properties)",
)
async def update_configuration(
    server_id: str,
    body: UpdateConfigRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("server.config.update")),
) -> ConfigProfileResponse:
    try:
        profile = await _facade(request).update_properties(
            server_id,
            body.properties,
            actor_id=identity.id,
        )
    except ValueError as exc:
        # El esquema valida contra reglas de dominio (p. ej. max-players > 40)
        # lanzando ValueError; se traduce a un error de validación (422).
        raise ValidationError(str(exc), context={"server_id": server_id}) from exc
    return _response(profile)