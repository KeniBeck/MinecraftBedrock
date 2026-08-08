"""Repositorio de Template en memoria (tests y MVP sin BBDD)."""

from __future__ import annotations

from datetime import datetime

from app.modules.template.domain.template import Template


class InMemoryTemplateRepository:
    """``TemplateRepositoryPort`` en memoria."""

    def __init__(self) -> None:
        self._templates: dict[str, Template] = {}

    async def save(self, template: Template) -> None:
        self._templates[template.id] = template

    async def get(self, template_id: str) -> Template | None:
        return self._templates.get(template_id)

    async def get_by_name(self, name: str) -> Template | None:
        for template in self._templates.values():
            if template.name == name:
                return template
        return None

    async def list(self) -> list[Template]:
        return sorted(self._templates.values(), key=_created_at)

    async def delete(self, template_id: str) -> None:
        self._templates.pop(template_id, None)


def _created_at(template: Template) -> datetime:
    return template.created_at or datetime.min
