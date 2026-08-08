"""Schemas HTTP del módulo Settings (vertical slice §16 ``modules/settings/api``).

Los DTOs de entrada/salida son de presentación; el valor viaja como JSON
arbitrario y la validación tipada ocurre en ``SettingsService.validate``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SettingValueRequest(BaseModel):
    value: Any
    description: str | None = Field(default=None, max_length=255)


class PatchSettingsRequest(BaseModel):
    values: dict[str, Any]


class SettingResponse(BaseModel):
    key: str
    value: Any
    category: str
    description: str | None = None
    type: str = "any"
    default: Any = None


class SettingsListResponse(BaseModel):
    settings: list[SettingResponse]
