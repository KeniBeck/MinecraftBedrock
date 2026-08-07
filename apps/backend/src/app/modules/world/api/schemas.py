"""Schemas HTTP del módulo World (vertical slice §16 ``modules/world/api``)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateWorldRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class DuplicateWorldRequest(BaseModel):
    target: str = Field(min_length=1, max_length=255)


class WorldResponse(BaseModel):
    id: str
    server_id: str
    name: str
    level_name: str
    size_bytes: int
    activated: bool
    created_at: datetime
    updated_at: datetime
