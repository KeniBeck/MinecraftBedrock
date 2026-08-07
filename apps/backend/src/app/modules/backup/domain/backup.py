"""Entidad ``Backup`` (Blueprint §3.4, Fase F paso 13).

Un ``Backup`` registra un **artefacto** de snapshot de un mundo de un servidor
guardado en el ``BackupStorePort`` (la referencia ``storage_ref`` es opaca para
el dominio). ``world_name`` es la unidad de dirección: Backup no depende del
módulo World (matriz §1.3) y no puede conocer su identidad; el blueprint §7.4
habla de ``world_id``, pero el módulo no puede importarlo (decisión §22, se
registra por nombre del directorio ``worlds/<nombre>``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class BackupState(StrEnum):
    """Ciclo de vida de un registro de backup (§8)."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CORRUPT = "corrupt"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class Backup:
    """Metadata de un artefacto de backup (el contenido vive en el store)."""

    id: str
    server_id: str
    world_name: str
    state: BackupState
    storage_ref: str
    created_at: datetime
    updated_at: datetime
    size_bytes: int = 0
    checksum: str = ""
    entries: list[str] = field(default_factory=list)
    duration_seconds: int | None = None
    protected: bool = False
    orphaned: bool = False
    error: str | None = None
