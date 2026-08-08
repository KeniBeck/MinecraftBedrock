"""Resultados de aplicación del módulo Template (Blueprint §4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.template.domain.template import Template


@dataclass(frozen=True, slots=True)
class TemplateView:
    """DTO público de una plantilla (metadata del artefacto, no el binario)."""

    id: str
    name: str
    version: str
    size_bytes: int
    origin_server_id: str | None
    origin_world: str | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class ApplyTemplateResult:
    """Resultado de aplicar una plantilla a un servidor."""

    template: TemplateView
    world_name: str


def template_to_view(template: Template) -> TemplateView:
    return TemplateView(
        id=template.id,
        name=template.name,
        version=template.version,
        size_bytes=template.size_bytes,
        origin_server_id=template.origin_server_id,
        origin_world=template.origin_world,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )
