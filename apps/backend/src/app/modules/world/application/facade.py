"""Facade pública del módulo World (Blueprint §3.3: create/import/export/
duplicate/delete/activate + list/sync). Los consumidores usan esta facade,
nunca el dominio directo.
"""

from __future__ import annotations

from app.modules.world.application.commands import (
    ActivateWorldCommand,
    CreateWorldCommand,
    DeleteWorldCommand,
    DuplicateWorldCommand,
    ExportWorldCommand,
    ImportWorldCommand,
    UpdateWorldCommand,
)
from app.modules.world.application.handlers import (
    SERVER_VERSION_CHANGED_TOPIC,
    VersionChangedHandler,
)
from app.modules.world.application.results import ExportWorldResult, WorldView, world_to_view
from app.modules.world.application.use_cases import (
    ActivateWorldUseCase,
    CreateWorldUseCase,
    DeleteWorldUseCase,
    DuplicateWorldUseCase,
    ExportWorldUseCase,
    ImportWorldUseCase,
    ScanWorldsUseCase,
    UpdateWorldUseCase,
    WorldDeps,
)
from app.modules.world.domain.repository import WorldRepositoryPort


class WorldFacade:
    """Puerta de entrada única al módulo World."""

    def __init__(self, deps: WorldDeps) -> None:
        self.deps = deps
        self._create = CreateWorldUseCase(deps)
        self._import = ImportWorldUseCase(deps)
        self._export = ExportWorldUseCase(deps)
        self._duplicate = DuplicateWorldUseCase(deps)
        self._delete = DeleteWorldUseCase(deps)
        self._activate = ActivateWorldUseCase(deps)
        self._update = UpdateWorldUseCase(deps)
        self._scan = ScanWorldsUseCase(deps)

    # -- operaciones ---------------------------------------------------------

    async def create(self, cmd: CreateWorldCommand) -> WorldView:
        return await self._create.create(cmd)

    async def import_world(self, cmd: ImportWorldCommand) -> WorldView:
        return await self._import.import_(cmd)

    async def export_world(self, cmd: ExportWorldCommand) -> ExportWorldResult:
        return await self._export.export(cmd)

    async def duplicate(self, cmd: DuplicateWorldCommand) -> WorldView:
        return await self._duplicate.duplicate(cmd)

    async def delete(self, cmd: DeleteWorldCommand) -> None:
        await self._delete.delete(cmd)

    async def activate(self, cmd: ActivateWorldCommand) -> WorldView:
        return await self._activate.activate(cmd)

    async def update(self, cmd: UpdateWorldCommand) -> WorldView:
        """Renombra y/o ajusta un mundo; reaplica la config si estaba activo."""
        return await self._update.update(cmd)

    # -- consultas -----------------------------------------------------------

    async def list_worlds(self, server_id: str) -> list[WorldView]:
        """Metadata de los mundos del servidor (cache del repositorio)."""
        repository: WorldRepositoryPort = self.deps.repository
        worlds = await repository.list_worlds(server_id)
        return [world_to_view(w) for w in worlds]

    async def sync(self, server_id: str) -> list[WorldView]:
        """Reconcilia la metadata con el storage; devuelve el listado reconciliado."""
        return await self._scan.sync(server_id)

    # -- eventos -------------------------------------------------------------

    def register_handlers(self) -> None:
        """Suscriptores del módulo sobre el bus (Blueprint §3.3)."""
        self.deps.bus.subscribe(SERVER_VERSION_CHANGED_TOPIC, VersionChangedHandler())
