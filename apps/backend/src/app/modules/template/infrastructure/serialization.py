"""Serialización del dominio Template ↔ filas (test sin BBDD)."""

from __future__ import annotations

from typing import Any

from app.modules.template.domain.template import Template
from app.modules.template.infrastructure.models import TemplateRow


def template_to_row(template: Template) -> dict[str, Any]:
    """Proyección de ``Template`` a los campos de ``TemplateRow``."""
    return {
        "id": template.id,
        "name": template.name,
        "version": template.version,
        "size_bytes": template.size_bytes,
        "origin_server_id": template.origin_server_id,
        "origin_world": template.origin_world,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def template_from_row(row: TemplateRow) -> Template:
    """Reconstruye ``Template`` desde una fila."""
    return Template(
        id=row.id,
        name=row.name,
        version=row.version,
        size_bytes=row.size_bytes,
        origin_server_id=row.origin_server_id,
        origin_world=row.origin_world,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
