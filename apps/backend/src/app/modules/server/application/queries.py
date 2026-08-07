"""Consultas (lecturas) del módulo Server."""

from __future__ import annotations

from app.kernel.ports.settings import SettingsPort
from app.modules.server.application.results import ServerView
from app.modules.server.application.use_cases import to_view
from app.modules.server.domain.repository import ServerRepositoryPort
from app.modules.server.domain.server import ServerId


class GetServerQuery:
    def __init__(self, repository: ServerRepositoryPort, settings: SettingsPort) -> None:
        self._repository = repository
        self._settings = settings

    async def execute(self, server_id: str) -> ServerView | None:
        server = await self._repository.get(ServerId(server_id))
        return to_view(server, self._settings) if server is not None else None


class ListServersQuery:
    def __init__(self, repository: ServerRepositoryPort, settings: SettingsPort) -> None:
        self._repository = repository
        self._settings = settings

    async def execute(self) -> list[ServerView]:
        servers = await self._repository.list_all()
        return [to_view(s, self._settings) for s in servers]
