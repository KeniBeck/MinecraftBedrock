"""Routers HTTP del módulo Template (vertical slice §16 ``modules/template/api``).

REST sobre la facade Template: capturar el estado de un servidor, listar/
consultar plantillas, aplicarlas (reproducir) a un servidor y eliminarlas. Es
el único módulo síncrono (request/response, sin eventos, hallazgo B5 del
blueprint). Auth por el patrón de los demás módulos: endpoints scoped a un
servidor reúsan ``require_server_action``; ``template.list``/``template.view``
van en ``READ_ACTIONS``; el resto es escritura (operator+).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.bootstrap.errors import http_error
from app.bootstrap.security import get_container, require_server_action
from app.kernel.ports.access import Identity
from app.modules.template.api.schemas import (
    ApplyTemplateRequest,
    CaptureTemplateRequest,
    TemplateResponse,
)
from app.modules.template.application.commands import (
    ApplyTemplateCommand,
    CaptureTemplateCommand,
    DeleteTemplateCommand,
)
from app.modules.template.application.facade import TemplateFacade
from app.modules.template.application.results import TemplateView

router = APIRouter(tags=["template"])


def _facade(request: Request) -> TemplateFacade:
    return get_container(request).template_facade


def _response(view: TemplateView) -> TemplateResponse:
    return TemplateResponse(
        id=view.id,
        name=view.name,
        version=view.version,
        size_bytes=view.size_bytes,
        origin_server_id=view.origin_server_id,
        origin_world=view.origin_world,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


async def _require_template(request: Request, template_id: str) -> TemplateView:
    view = await _facade(request).get_template(template_id)
    if view is None:
        raise http_error(
            404,
            "TEMPLATE.NOT_FOUND",
            "La plantilla no existe",
            {"template_id": template_id},
        )
    return view


@router.post(
    "/servers/{server_id}/templates/capture",
    response_model=TemplateResponse,
    status_code=201,
    summary="Capturar el estado del servidor como plantilla (.mctemplate)",
)
async def capture_template(
    server_id: str,
    body: CaptureTemplateRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("template.capture")),
) -> TemplateResponse:
    view = await _facade(request).capture(
        CaptureTemplateCommand(
            server_id=server_id,
            name=body.name,
            actor_id=identity.id,
        )
    )
    return _response(view)


@router.get(
    "/servers/{server_id}/templates",
    response_model=list[TemplateResponse],
    summary="Listar plantillas del panel",
)
async def list_templates(
    server_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("template.list")),
) -> list[TemplateResponse]:
    del identity, server_id
    views = await _facade(request).list_templates()
    return [_response(view) for view in views]


@router.get(
    "/servers/{server_id}/templates/{template_id}",
    response_model=TemplateResponse,
    summary="Detalle de una plantilla",
)
async def get_template(
    server_id: str,
    template_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("template.view")),
) -> TemplateResponse:
    del server_id
    return _response(await _require_template(request, template_id))


@router.post(
    "/servers/{server_id}/templates/{template_id}/apply",
    response_model=TemplateResponse,
    summary="Aplicar (reproducir) una plantilla sobre el servidor",
)
async def apply_template(
    server_id: str,
    template_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("template.apply")),
    body: ApplyTemplateRequest | None = None,
) -> TemplateResponse:
    result = await _facade(request).apply(
        ApplyTemplateCommand(
            server_id=server_id,
            template_id=template_id,
            world_name=body.world_name if body is not None else None,
            actor_id=identity.id,
        )
    )
    return _response(result.template)


@router.delete(
    "/servers/{server_id}/templates/{template_id}",
    status_code=204,
    summary="Eliminar una plantilla",
)
async def delete_template(
    server_id: str,
    template_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("template.delete")),
) -> None:
    del server_id
    await _require_template(request, template_id)
    await _facade(request).delete(
        DeleteTemplateCommand(template_id=template_id, actor_id=identity.id)
    )
