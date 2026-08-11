"""Repositorio de World en memoria (tests y MVP sin BBDD)."""

from __future__ import annotations

from app.modules.world.domain.world import World


class InMemoryWorldRepository:
    """``WorldRepositoryPort`` en memoria."""

    def __init__(self) -> None:
        self._worlds: dict[tuple[str, str], World] = {}

    async def get_world(self, server_id: str, name: str) -> World | None:
        return self._worlds.get((server_id, name))

    async def list_worlds(self, server_id: str) -> list[World]:
        worlds = [w for (sid, _), w in self._worlds.items() if sid == server_id]
        worlds.sort(key=lambda w: w.name)
        return worlds

    async def save_world(self, world: World) -> None:
        self._worlds[(world.server_id, world.name)] = world

    async def delete_world(self, server_id: str, name: str) -> None:
        self._worlds.pop((server_id, name), None)

    async def deactivate_worlds(self, server_id: str) -> None:
        for (sid, _), world in list(self._worlds.items()):
            if sid == server_id:
                self._worlds[(sid, world.name)] = _deactivate(world)


def _deactivate(world: World) -> World:
    return World(
        id=world.id,
        server_id=world.server_id,
        name=world.name,
        level_name=world.level_name,
        size_bytes=world.size_bytes,
        activated=False,
        created_at=world.created_at,
        updated_at=world.updated_at,
        seed=world.seed,
        gamemode=world.gamemode,
        difficulty=world.difficulty,
        view_distance=world.view_distance,
    )
