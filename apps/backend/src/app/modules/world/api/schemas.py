"""Schemas HTTP del módulo World (vertical slice §16 ``modules/world/api``)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

WorldGameMode = Literal["survival", "creative", "adventure"]
WorldDifficulty = Literal["peaceful", "easy", "normal", "hard"]


class CreateWorldRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    seed: str | None = Field(default=None, max_length=64)
    gamemode: WorldGameMode | None = None
    difficulty: WorldDifficulty | None = None
    view_distance: int | None = Field(default=None, ge=2, le=64)


class UpdateWorldRequest(BaseModel):
    """Actualización parcial: solo cambian los campos presentes.

    ``name`` renombra el mundo (directorio + metadata); los ajustes opcionales
    se actualizan si vienen. ``None`` en un ajuste = no cambiar (no se soporta
    limpiar un ajuste a ``None`` en esta versión).
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    seed: str | None = Field(default=None, max_length=64)
    gamemode: WorldGameMode | None = None
    difficulty: WorldDifficulty | None = None
    view_distance: int | None = Field(default=None, ge=2, le=64)


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
    seed: str | None = None
    gamemode: str | None = None
    difficulty: str | None = None
    view_distance: int | None = None
