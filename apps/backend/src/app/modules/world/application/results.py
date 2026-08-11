"""Vistas de salida de los use cases del módulo World (proyecciones, §4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO

from app.modules.world.domain.world import World


@dataclass(frozen=True, slots=True)
class WorldView:
    """Proyección de un mundo para consumidores externos (facade pública)."""

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


@dataclass(frozen=True, slots=True)
class ExportWorldResult:
    """Resultado de exportar un mundo: vista + stream (zip) de la copia.

    ``consistent`` indica si el snapshot es consistente (decisión del paso de
    cierre): ``True`` si el servidor estaba detenido o ``save hold`` fue
    aceptado por Console; ``False`` si el servidor corría y el ``save hold``
    falló (el snapshot se exporta igual, best-effort, §22).
    """

    world: WorldView
    stream: BinaryIO
    size_bytes: int
    consistent: bool


def world_to_view(world: World) -> WorldView:
    """Proyecta un mundo del dominio a su vista de presentación."""
    return WorldView(
        id=world.id,
        server_id=world.server_id,
        name=world.name,
        level_name=world.level_name,
        size_bytes=world.size_bytes,
        activated=world.activated,
        created_at=world.created_at,
        updated_at=world.updated_at,
        seed=world.seed,
        gamemode=world.gamemode,
        difficulty=world.difficulty,
        view_distance=world.view_distance,
    )
