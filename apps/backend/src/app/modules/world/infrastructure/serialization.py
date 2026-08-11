"""Serialización del dominio World ↔ filas (test sin BBDD)."""

from __future__ import annotations

from typing import Any

from app.modules.world.domain.world import World
from app.modules.world.infrastructure.models import WorldRow


def world_to_row(world: World) -> dict[str, Any]:
    """Proyección de ``World`` a los campos de ``WorldRow``."""
    return {
        "id": world.id,
        "server_id": world.server_id,
        "name": world.name,
        "level_name": world.level_name,
        "size_bytes": world.size_bytes,
        "activated": world.activated,
        "created_at": world.created_at,
        "updated_at": world.updated_at,
        "seed": world.seed,
        "gamemode": world.gamemode,
        "difficulty": world.difficulty,
        "view_distance": world.view_distance,
    }


def world_from_row(row: WorldRow) -> World:
    """Reconstruye ``World`` desde una fila."""
    return World(
        id=row.id,
        server_id=row.server_id,
        name=row.name,
        level_name=row.level_name,
        size_bytes=row.size_bytes,
        activated=row.activated,
        created_at=row.created_at,
        updated_at=row.updated_at,
        seed=row.seed,
        gamemode=row.gamemode,
        difficulty=row.difficulty,
        view_distance=row.view_distance,
    )
