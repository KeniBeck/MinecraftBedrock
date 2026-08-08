"""Puerto de repositorio del módulo Template (Blueprint §4.8)."""

from __future__ import annotations

from typing import Protocol

from app.modules.template.domain.template import Template


class TemplateRepositoryPort(Protocol):
    """Persistencia de la metadata de plantillas."""

    async def save(self, template: Template) -> None:
        """Inserta o actualiza (upsert) una plantilla."""

    async def get(self, template_id: str) -> Template | None:
        """Devuelve una plantilla por id, o ``None``."""

    async def get_by_name(self, name: str) -> Template | None:
        """Devuelve la plantilla con ese nombre exacto, o ``None``."""

    async def list(self) -> list[Template]:
        """Lista todas las plantillas."""

    async def delete(self, template_id: str) -> None:
        """Elimina la metadata (no el artefacto; eso lo hace el store)."""
