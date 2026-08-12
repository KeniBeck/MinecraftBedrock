"""Puerto de persistencia del módulo Player (Blueprint §3.5).

``Player`` (caché de identidad + playtime acumulado) y ``PlaySession``
(presencia por servidor). Los bans viven en agregados propios
(``GlobalBan``/``ServerBan``, ADR-011) a través de ``PlayerBanRepositoryPort``.
La implementación durable es Postgres; en memoria para tests. Sin FKs a otros
módulos (bounded contexts, mismo criterio que IAM/Configuration).
"""

from __future__ import annotations

from typing import Protocol

from app.modules.player.domain.bans import GlobalBan, ServerBan
from app.modules.player.domain.player import Player
from app.modules.player.domain.session import PlaySession


class PlayerRepositoryPort(Protocol):
    """Persistencia de jugadores y sesiones de juego."""

    async def get_player(self, xuid: str) -> Player | None: ...

    async def get_player_by_name(self, name: str) -> Player | None: ...

    async def search_players(self, term: str, limit: int = 10) -> list[Player]:
        """Búsqueda por gamertag parcial (case-insensitive), más recientes primero."""

    async def save_player(self, player: Player) -> None: ...

    async def get_open_session(self, server_id: str, xuid: str) -> PlaySession | None: ...

    async def list_open_sessions_by_xuid(self, xuid: str) -> list[PlaySession]:
        """Sesiones abiertas del jugador en todos los servidores (kick global)."""

    async def save_session(self, session: PlaySession) -> None: ...

    async def list_open_sessions(self, server_id: str) -> list[PlaySession]: ...

    async def list_sessions(self, xuid: str, limit: int = 20) -> list[PlaySession]: ...


class PlayerBanRepositoryPort(Protocol):
    """Persistencia de bans persistentes (globales y por servidor)."""

    # -- global -----------------------------------------------------------

    async def get_global_ban(self, ban_id: str) -> GlobalBan | None: ...

    async def get_global_ban_by_gamertag(self, gamertag: str) -> GlobalBan | None: ...

    async def get_active_global_ban_by_xuid(self, xuid: str) -> GlobalBan | None: ...

    async def get_active_global_ban_by_gamertag(self, gamertag: str) -> GlobalBan | None: ...

    async def list_global_bans(self) -> list[GlobalBan]:
        """Todos los bans globales, más recientes primero."""

    async def save_global_ban(self, ban: GlobalBan) -> None: ...

    async def delete_global_ban(self, ban_id: str) -> bool: ...

    # -- por servidor -----------------------------------------------------

    async def get_server_ban(self, server_id: str, ban_id: str) -> ServerBan | None: ...

    async def get_server_ban_by_gamertag(
        self, server_id: str, gamertag: str
    ) -> ServerBan | None: ...

    async def get_active_server_ban_by_xuid(
        self, server_id: str, xuid: str
    ) -> ServerBan | None: ...

    async def get_active_server_ban_by_gamertag(
        self, server_id: str, gamertag: str
    ) -> ServerBan | None: ...

    async def list_server_bans(self, server_id: str) -> list[ServerBan]:
        """Bans por servidor, más recientes primero."""

    async def save_server_ban(self, ban: ServerBan) -> None: ...

    async def delete_server_ban(self, server_id: str, ban_id: str) -> bool: ...
