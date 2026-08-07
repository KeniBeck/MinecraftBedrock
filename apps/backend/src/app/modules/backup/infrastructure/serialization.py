"""Serialización del dominio Backup ↔ filas (test sin BBDD)."""

from __future__ import annotations

from typing import Any

from app.modules.backup.domain.backup import Backup, BackupState
from app.modules.backup.infrastructure.models import BackupRow


def backup_to_row(backup: Backup) -> dict[str, Any]:
    """Proyección de ``Backup`` a los campos de ``BackupRow``."""
    return {
        "id": backup.id,
        "server_id": backup.server_id,
        "world_name": backup.world_name,
        "state": backup.state.value,
        "storage_ref": backup.storage_ref,
        "size_bytes": backup.size_bytes,
        "checksum": backup.checksum,
        "entries": backup.entries,
        "duration_seconds": backup.duration_seconds,
        "protected": backup.protected,
        "orphaned": backup.orphaned,
        "error": backup.error,
        "created_at": backup.created_at,
        "updated_at": backup.updated_at,
    }


def backup_from_row(row: BackupRow) -> Backup:
    """Reconstruye ``Backup`` desde una fila."""
    return Backup(
        id=row.id,
        server_id=row.server_id,
        world_name=row.world_name,
        state=BackupState(row.state),
        storage_ref=row.storage_ref,
        size_bytes=row.size_bytes,
        checksum=row.checksum,
        entries=list(row.entries or []),
        duration_seconds=row.duration_seconds,
        protected=row.protected,
        orphaned=row.orphaned,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
