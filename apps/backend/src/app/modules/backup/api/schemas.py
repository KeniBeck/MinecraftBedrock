"""Schemas HTTP del módulo Backup (vertical slice §16 ``modules/backup/api``)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateBackupRequest(BaseModel):
    world_name: str = Field(min_length=1, max_length=255)
    protected: bool = False


class PruneBackupRequest(BaseModel):
    keep_last_n: int = Field(default=10, ge=0)


class BackupResponse(BaseModel):
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
