"""Puerto de persistencia del módulo World (Blueprint §3.3).

Metadata de mundos (la fuente de verdad del contenido es el filesystem vía
``ServerStoragePort``). Sin FKs a otros módulos (bounded contexts, mismo
criterio que Player/IAM/Configuration).
"""

from __future__ import annotations

from typing import Protocol

from app.modules.world.domain.world import World


class WorldRepositoryPort(Protocol):
    """Persistencia de la metadata de mundos de un servidor."""

    async def get_world(self, server_id: str, name: str) -> World | None: ...

    async def list_worlds(self, server_id: str) -> list[World]: ...

    async def save_world(self, world: World) -> None: ...

    async def delete_world(self, server_id: str, name: str) -> None: ...

    async def deactivate_worlds(self, server_id: str) -> None:
        """Pone ``activated=False`` a todos los mundos del servidor."""
