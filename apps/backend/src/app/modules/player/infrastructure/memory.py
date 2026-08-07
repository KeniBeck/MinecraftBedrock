"""Repositorio de Player en memoria (tests y MVP sin BBDD)."""

from __future__ import annotations

from app.modules.player.domain.player import Player
from app.modules.player.domain.session import PlaySession


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

    async def list_sessions(self, xuid: str, limit: int = 20) -> list[PlaySession]:
        sessions = [s for s in self._sessions.values() if s.xuid == xuid]
        sessions.sort(key=lambda s: s.joined_at, reverse=True)
        return sessions[:limit]
