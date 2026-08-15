"""Schemas HTTP del módulo Configuration (vertical slice §16)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ConfigProfileResponse(BaseModel):
    """Config deseada de un servidor (properties, versión y revisión)."""

    server_id: str
    version: str
    config_rev: int
    properties: dict[str, str]
    applied: dict[str, str] | None = None
    applied_at: datetime | None = None
    updated_at: datetime


class UpdateConfigRequest(BaseModel):
    """Cuerpo de ``PUT /servers/{id}/configuration`` (server.properties)."""

    properties: dict[str, str]