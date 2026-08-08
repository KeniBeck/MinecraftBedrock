"""Repositorio de Player en memoria (tests y MVP sin BBDD)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.player.domain.bans import GlobalBan, ServerBan, normalize_gamertag
from app.modules.player.domain.player import Player
from app.modules.player.domain.session import PlaySession


def _now() -> datetime:
    return datetime.now(UTC)


class InMemoryPlayerRepository:
    """``PlayerRepositoryPort`` en memoria."""

    def __init__(self) -> None:
        self._players: dict[str, Player] = {}
        self._sessions: dict[str, PlaySession] = {}

    async def get_player(self, xuid: str) -> Player | None:
        return self._players.get(xuid)

    async def get_player_by_name(self, name: str) -> Player | None:
        matches = [p for p in self._players.values() if p.name == name]
        if not matches:
            return None
        return max(matches, key=lambda p: p.last_seen_at)

    async def save_player(self, player: Player) -> None:
        self._players[player.xuid] = player

    async def get_open_session(self, server_id: str, xuid: str) -> PlaySession | None:
        for session in self._sessions.values():
            if session.server_id == server_id and session.xuid == xuid and session.left_at is None:
                return session
        return None

    async def save_session(self, session: PlaySession) -> None:
        self._sessions[session.id] = session

    async def list_open_sessions(self, server_id: str) -> list[PlaySession]:
        return [
            session
            for session in self._sessions.values()
            if session.server_id == server_id and session.left_at is None
        ]

    async def list_open_sessions_by_xuid(self, xuid: str) -> list[PlaySession]:
        return [
            session
            for session in self._sessions.values()
            if session.xuid == xuid and session.left_at is None
        ]

    async def list_sessions(self, xuid: str, limit: int = 20) -> list[PlaySession]:
        sessions = [s for s in self._sessions.values() if s.xuid == xuid]
        sessions.sort(key=lambda s: s.joined_at, reverse=True)
        return sessions[:limit]


class InMemoryPlayerBanRepository:
    """``PlayerBanRepositoryPort`` en memoria (filtra vigencia por ``expires_at``)."""

    def __init__(self) -> None:
        self._global_bans: dict[str, GlobalBan] = {}
        self._server_bans: dict[str, ServerBan] = {}

    # -- global -----------------------------------------------------------

    async def get_global_ban(self, ban_id: str) -> GlobalBan | None:
        return self._global_bans.get(ban_id)

    async def get_global_ban_by_gamertag(self, gamertag: str) -> GlobalBan | None:
        key = normalize_gamertag(gamertag)
        for ban in self._global_bans.values():
            if normalize_gamertag(ban.gamertag) == key:
                return ban
        return None

    async def get_active_global_ban_by_xuid(self, xuid: str) -> GlobalBan | None:
        now = _now()
        for ban in self._global_bans.values():
            if ban.xuid == xuid and ban.is_active(now):
                return ban
        return None

    async def get_active_global_ban_by_gamertag(self, gamertag: str) -> GlobalBan | None:
        now = _now()
        key = normalize_gamertag(gamertag)
        for ban in self._global_bans.values():
            if normalize_gamertag(ban.gamertag) == key and ban.is_active(now):
                return ban
        return None

    async def save_global_ban(self, ban: GlobalBan) -> None:
        self._global_bans[ban.id] = ban

    async def delete_global_ban(self, ban_id: str) -> bool:
        return self._global_bans.pop(ban_id, None) is not None

    # -- por servidor -----------------------------------------------------

    async def get_server_ban(self, server_id: str, ban_id: str) -> ServerBan | None:
        ban = self._server_bans.get(ban_id)
        if ban is not None and ban.server_id == server_id:
            return ban
        return None

    async def get_server_ban_by_gamertag(self, server_id: str, gamertag: str) -> ServerBan | None:
        key = normalize_gamertag(gamertag)
        for ban in self._server_bans.values():
            if ban.server_id == server_id and normalize_gamertag(ban.gamertag) == key:
                return ban
        return None

    async def get_active_server_ban_by_xuid(self, server_id: str, xuid: str) -> ServerBan | None:
        now = _now()
        for ban in self._server_bans.values():
            if ban.server_id == server_id and ban.xuid == xuid and ban.is_active(now):
                return ban
        return None

    async def get_active_server_ban_by_gamertag(
        self, server_id: str, gamertag: str
    ) -> ServerBan | None:
        now = _now()
        key = normalize_gamertag(gamertag)
        for ban in self._server_bans.values():
            if (
                ban.server_id == server_id
                and normalize_gamertag(ban.gamertag) == key
                and ban.is_active(now)
            ):
                return ban
        return None

    async def save_server_ban(self, ban: ServerBan) -> None:
        self._server_bans[ban.id] = ban

    async def delete_server_ban(self, server_id: str, ban_id: str) -> bool:
        ban = self._server_bans.get(ban_id)
        if ban is None or ban.server_id != server_id:
            return False
        del self._server_bans[ban_id]
        return True
