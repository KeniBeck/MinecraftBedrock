"""Puerto de persistencia del módulo Player (Blueprint §3.5).

``Player`` (caché de identidad + playtime acumulado) y ``PlaySession``
(presencia por servidor). La implementación durable es Postgres; en memoria
para tests. Sin FKs a otros módulos (bounded contexts, mismo criterio que IAM/
Configuration).
"""

from __future__ import annotations

from typing import Protocol

from app.modules.player.domain.player import Player
from app.modules.player.domain.session import PlaySession


class PlayerRepositoryPort(Protocol):
    """Persistencia de jugadores y sesiones de juego."""

    async def get_player(self, xuid: str) -> Player | None: ...

    async def get_player_by_name(self, name: str) -> Player | None: ...

    async def save_player(self, player: Player) -> None: ...

    async def get_open_session(self, server_id: str, xuid: str) -> PlaySession | None: ...

    async def save_session(self, session: PlaySession) -> None: ...

    async def list_open_sessions(self, server_id: str) -> list[PlaySession]: ...

    async def list_sessions(self, xuid: str, limit: int = 20) -> list[PlaySession]: ...
