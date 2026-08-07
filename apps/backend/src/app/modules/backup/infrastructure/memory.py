"""Repositorio de Backup en memoria (tests y MVP sin BBDD)."""

from __future__ import annotations

from app.modules.backup.domain.backup import Backup


class InMemoryBackupRepository:
    """``BackupRepositoryPort`` en memoria."""

    def __init__(self) -> None:
        self._backups: dict[str, Backup] = {}

    async def save_backup(self, backup: Backup) -> None:
        self._backups[backup.id] = backup

    async def get_backup(self, backup_id: str) -> Backup | None:
        return self._backups.get(backup_id)

    async def list_backups(
        self,
        server_id: str,
        *,
        world_name: str | None = None,
        limit: int = 50,
    ) -> list[Backup]:
        records = [
            backup
            for backup in self._backups.values()
            if backup.server_id == server_id
            and (world_name is None or backup.world_name == world_name)
        ]
        records.sort(key=lambda backup: backup.created_at, reverse=True)
        return records[:limit]

    async def delete_backup(self, backup_id: str) -> None:
        self._backups.pop(backup_id, None)

    async def mark_orphaned(self, server_id: str, world_name: str) -> None:
        for backup_id, backup in list(self._backups.items()):
            if backup.server_id == server_id and backup.world_name == world_name:
                self._backups[backup_id] = _orphan(backup)


def _orphan(backup: Backup) -> Backup:
    return Backup(
        id=backup.id,
        server_id=backup.server_id,
        world_name=backup.world_name,
        state=backup.state,
        storage_ref=backup.storage_ref,
        created_at=backup.created_at,
        updated_at=backup.updated_at,
        size_bytes=backup.size_bytes,
        checksum=backup.checksum,
        entries=backup.entries,
        duration_seconds=backup.duration_seconds,
        protected=backup.protected,
        orphaned=True,
        error=backup.error,
    )
