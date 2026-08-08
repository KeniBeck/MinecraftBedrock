"""Schemas HTTP del módulo Template (vertical slice §16 ``modules/template/api``)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CaptureTemplateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ApplyTemplateRequest(BaseModel):
    world_name: str | None = Field(default=None, min_length=1, max_length=255)


class TemplateResponse(BaseModel):
    id: str
    name: str
    version: str
    size_bytes: int
    origin_server_id: str | None
    origin_world: str | None
    created_at: datetime | None
    updated_at: datetime | None
