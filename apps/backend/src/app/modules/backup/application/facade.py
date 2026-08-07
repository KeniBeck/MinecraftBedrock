"""Facade pública del módulo Backup (Blueprint §3.4: createBackup, restoreBackup,
prune, validate). Los consumidores usan esta facade, nunca las entidades.
"""

from __future__ import annotations

from app.modules.backup.application.commands import (
    CreateBackupCommand,
    DeleteBackupCommand,
    PruneBackupCommand,
    RestoreBackupCommand,
    ValidateBackupCommand,
)
from app.modules.backup.application.handlers import WorldDeletedHandler
from app.modules.backup.application.results import (
    BackupDownload,
    BackupView,
    backup_to_view,
)
from app.modules.backup.application.use_cases import (
    BackupDeps,
    CreateBackupUseCase,
    DeleteBackupUseCase,
    PruneBackupUseCase,
    RestoreBackupUseCase,
    ValidateBackupUseCase,
)
from app.modules.world.domain.events import WORLD_DELETED_TOPIC


class BackupFacade:
    """Puerta de entrada única al módulo Backup."""

    def __init__(self, deps: BackupDeps) -> None:
        self.deps = deps
        self._create = CreateBackupUseCase(deps)
        self._restore = RestoreBackupUseCase(deps)
        self._prune = PruneBackupUseCase(deps)
        self._validate = ValidateBackupUseCase(deps)
        self._delete = DeleteBackupUseCase(deps)

    async def create_backup(self, cmd: CreateBackupCommand) -> BackupView:
        return await self._create.create(cmd)

    async def restore_backup(self, cmd: RestoreBackupCommand) -> BackupView:
        return await self._restore.restore(cmd)

    async def prune(self, cmd: PruneBackupCommand) -> list[BackupView]:
        return await self._prune.prune(cmd)

    async def validate(self, cmd: ValidateBackupCommand) -> BackupView:
        return await self._validate.validate(cmd)

    async def delete_backup(self, cmd: DeleteBackupCommand) -> None:
        await self._delete.delete(cmd)

    async def list_backups(
        self,
        server_id: str,
        *,
        world_name: str | None = None,
        limit: int = 50,
    ) -> list[BackupView]:
        records = await self.deps.repository.list_backups(
            server_id,
            world_name=world_name,
            limit=limit,
        )
        return [backup_to_view(record) for record in records]

    async def get_backup(self, backup_id: str) -> BackupView | None:
        record = await self.deps.repository.get_backup(backup_id)
        if record is None:
            return None
        return backup_to_view(record)

    async def download(self, backup_id: str) -> BackupDownload | None:
        """Abre el artefacto de un backup para descarga (stream, sin cargar en memoria).

        El caller es responsable de cerrar ``BackupDownload.stream``.
        """
        record = await self.deps.repository.get_backup(backup_id)
        if record is None:
            return None
        return BackupDownload(
            backup=backup_to_view(record),
            stream=self.deps.store.get(record.storage_ref),
        )

    def register_handlers(self) -> None:
        """Suscriptores del módulo sobre el bus (Blueprint §3.4)."""
        self.deps.bus.subscribe(WORLD_DELETED_TOPIC, WorldDeletedHandler(self.deps.repository))
