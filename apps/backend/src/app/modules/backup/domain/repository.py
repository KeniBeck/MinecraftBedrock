"""Puerto de repositorio del módulo Backup (Blueprint §4.8)."""

from __future__ import annotations

from typing import Protocol

from app.modules.backup.domain.backup import Backup


class BackupRepositoryPort(Protocol):
    """Persistencia de registros de backup (el artefacto vive en el store)."""

    async def save_backup(self, backup: Backup) -> None:
        """Inserta o actualiza (upsert) un registro de backup."""

    async def get_backup(self, backup_id: str) -> Backup | None:
        """Devuelve un registro por id, o ``None``."""

    async def list_backups(
        self,
        server_id: str,
        *,
        world_name: str | None = None,
        limit: int = 50,
    ) -> list[Backup]:
        """Lista registros de un servidor, más recientes primero (para prune)."""

    async def delete_backup(self, backup_id: str) -> None:
        """Elimina el registro (no el artefacto; eso lo hace el store)."""

    async def mark_orphaned(self, server_id: str, world_name: str) -> None:
        """Marca huérfanos los backups del mundo eliminado (§9.3)."""
