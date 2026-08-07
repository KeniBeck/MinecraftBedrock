"""Repositorio en memoria del agregado ``Server`` (Fase B, sin BBDD).

Implementa ``ServerRepositoryPort``. Persistencia en memoria para el núcleo;
una implementación durable (SQLite/Postgres) llegará con el storage del panel.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.server.domain.errors import ServerNotFoundError
from app.modules.server.domain.server import Server, ServerId


class InMemoryServerRepository:
    """Almacena servidores en un dict; no sobrevive a reinicios del proceso."""

    def __init__(self) -> None:
        self._servers: dict[str, Server] = {}

    async def save(self, server: Server) -> None:
        self._servers[server.id.value] = server

    async def get(self, server_id: ServerId) -> Server | None:
        return self._servers.get(server_id.value)

    async def get_required(self, server_id: ServerId) -> Server:
        server = await self.get(server_id)
        if server is None:
            raise ServerNotFoundError(
                f"Servidor no encontrado: {server_id.value}",
                context={"server_id": server_id.value},
            )
        return server

    async def list_all(self) -> Sequence[Server]:
        return list(self._servers.values())
