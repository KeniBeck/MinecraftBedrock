"""Puerto de persistencia del dominio Server (Blueprint §4.8, TDD §13.2).

Protocol estructural implementado por infraestructura (p. ej.
``InMemoryServerRepository``). El dominio declara la interfaz; el módulo la
define aquí para no depender de Infrastructure.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.modules.server.domain.server import Server, ServerId


class ServerRepositoryPort(Protocol):
    """Persistencia del agregado ``Server``."""

    async def save(self, server: Server) -> None: ...

    async def get(self, server_id: ServerId) -> Server | None: ...

    async def get_required(self, server_id: ServerId) -> Server:
        """Igual que ``get`` pero lanza ``ServerNotFoundError`` si no existe."""
        ...

    async def list_all(self) -> Sequence[Server]: ...
