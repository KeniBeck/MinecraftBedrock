"""Resultados de aplicación del módulo Backup (Blueprint §4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO

from app.modules.backup.domain.backup import Backup


@dataclass(frozen=True, slots=True)
class BackupView:
    """DTO público de un registro de backup (sin detalles internos del store)."""

    id: str
    server_id: str
    world_name: str
    state: str
    size_bytes: int
    checksum: str
    entries: list[str]
    duration_seconds: int | None
    protected: bool
    orphaned: bool
    error: str | None
    created_at: datetime
    updated_at: datetime


def backup_to_view(backup: Backup) -> BackupView:
    return BackupView(
        id=backup.id,
        server_id=backup.server_id,
        world_name=backup.world_name,
        state=backup.state.value,
        size_bytes=backup.size_bytes,
        checksum=backup.checksum,
        entries=list(backup.entries),
        duration_seconds=backup.duration_seconds,
        protected=backup.protected,
        orphaned=backup.orphaned,
        error=backup.error,
        created_at=backup.created_at,
        updated_at=backup.updated_at,
    )


@dataclass(frozen=True, slots=True)
class BackupDownload:
    """Backup + stream abierto del artefacto (para descarga, §16)."""

    backup: BackupView
    stream: BinaryIO
