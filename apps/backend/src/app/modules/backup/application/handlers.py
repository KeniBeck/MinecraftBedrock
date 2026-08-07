"""Handlers de eventos que consume el módulo Backup (Blueprint §9.3, §9.4).

Backup consume ``WORLD.DELETED`` para marcar **huérfanos** los backups del
mundo eliminado (el prune los trata por política; §8.7). Los handlers son
defensivos: nunca cortan el bus (mismo criterio que World, §22).
"""

from __future__ import annotations

from app.kernel.events.event import DomainEvent
from app.modules.backup.domain.repository import BackupRepositoryPort


class WorldDeletedHandler:
    """``WORLD.DELETED`` → marca huérfanos los backups de ese mundo."""

    def __init__(self, repository: BackupRepositoryPort) -> None:
        self._repository = repository

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id
        name = event.payload.get("name")
        if not server_id or not isinstance(name, str):
            return
        await self._repository.mark_orphaned(server_id, name)
