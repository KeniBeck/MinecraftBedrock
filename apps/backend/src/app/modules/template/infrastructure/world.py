"""Adapter de ``WorldGateway`` sobre la facade World (Blueprint §3.11).

Template consulta aquí el mundo activo de un servidor (en vez de leerlo de
Configuration): el estado real se gestiona en World (``world_metadata.activated``
= true) y se inyecta al RuntimeSpec vía ``WORLD.ACTIVATED`` (§25), nunca pasa
por Configuration. Sigue el criterio de Scheduler: el consumidor depende de un
port estructural, la integración con el otro módulo vive en un adaptador.
"""

from __future__ import annotations

from app.modules.template.application.ports import WorldGateway
from app.modules.world.application.facade import WorldFacade


class WorldFacadeGateway(WorldGateway):
    """``WorldGateway`` delegando en ``WorldFacade.list_worlds``."""

    def __init__(self, facade: WorldFacade) -> None:
        self._facade = facade

    async def active_world(self, server_id: str) -> str | None:
        worlds = await self._facade.list_worlds(server_id)
        for world in worlds:
            if world.activated:
                return world.name
        return None
