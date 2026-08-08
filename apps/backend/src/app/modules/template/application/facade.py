"""Facade pública del módulo Template (Blueprint §3.11).

Los consumidores usan esta facade, nunca el dominio directo: capturar, listar,
consultar, aplicar y eliminar plantillas. El módulo es síncrono (sin eventos).
``default_template`` satisface el protocolo ``TemplateReader`` que predefine
Server (integración opcional en la creación de servidores, aún sin uso).
"""

from __future__ import annotations

from app.modules.template.application.commands import (
    ApplyTemplateCommand,
    CaptureTemplateCommand,
    DeleteTemplateCommand,
)
from app.modules.template.application.results import (
    ApplyTemplateResult,
    TemplateView,
)
from app.modules.template.application.use_cases import (
    ApplyTemplateUseCase,
    CaptureTemplateUseCase,
    DeleteTemplateUseCase,
    GetTemplateUseCase,
    ListTemplatesUseCase,
    TemplateDeps,
)


class TemplateFacade:
    """Puerta de entrada única al módulo Template."""

    def __init__(self, deps: TemplateDeps) -> None:
        self.deps = deps
        self._capture = CaptureTemplateUseCase(deps)
        self._apply = ApplyTemplateUseCase(deps)
        self._list = ListTemplatesUseCase(deps)
        self._get = GetTemplateUseCase(deps)
        self._delete = DeleteTemplateUseCase(deps)

    async def capture(self, cmd: CaptureTemplateCommand) -> TemplateView:
        return await self._capture.capture(cmd)

    async def apply(self, cmd: ApplyTemplateCommand) -> ApplyTemplateResult:
        return await self._apply.apply(cmd)

    async def list_templates(self) -> list[TemplateView]:
        return await self._list.list_templates()

    async def get_template(self, template_id: str) -> TemplateView | None:
        return await self._get.get(template_id)

    async def delete(self, cmd: DeleteTemplateCommand) -> None:
        await self._delete.delete(cmd)

    async def default_template(self) -> str | None:
        """Plantilla por defecto (protocolo ``TemplateReader`` de Server).

        Regresa ``None`` hasta que exista una política de "plantilla por
        defecto" marcada explícitamente (fuera de alcance de este paso).
        """
        return None
