"""Facade pública del módulo Permission (Blueprint §3.6).

Expone las operaciones de allowlist y permisos; los consumidores usan esta
facade, nunca el dominio directo.
"""

from __future__ import annotations

from app.modules.permission.application import use_cases
from app.modules.permission.application.handlers import AllowlistXuidResolver
from app.modules.permission.application.use_cases import PermissionDeps
from app.modules.permission.domain.entities import (
    AllowlistEntry,
    PermissionEntry,
    PermissionLevel,
)


class PermissionFacade:
    """Puerta de entrada única al módulo Permission."""

    def __init__(self, deps: PermissionDeps) -> None:
        self.deps = deps
        self._xuid_resolver = AllowlistXuidResolver(deps.storage, deps.bus)

    async def add_to_allowlist(
        self,
        server_id: str,
        name: str,
        xuid: str,
        ignores_player_limit: bool = False,
    ) -> AllowlistEntry:
        return await use_cases.add_to_allowlist(
            self.deps, server_id, name, xuid, ignores_player_limit
        )

    async def remove_from_allowlist(self, server_id: str, xuid: str) -> None:
        await use_cases.remove_from_allowlist(self.deps, server_id, xuid)

    async def list_allowlist(self, server_id: str) -> list[AllowlistEntry]:
        return await use_cases.list_allowlist(self.deps, server_id)

    async def set_allowlist_enabled(
        self,
        server_id: str,
        enabled: bool,
        *,
        actor_id: str | None = None,
    ) -> None:
        await use_cases.set_allowlist_enabled(self.deps, server_id, enabled, actor_id=actor_id)

    async def set_permission_level(
        self,
        server_id: str,
        xuid: str,
        level: PermissionLevel,
        *,
        actor_id: str | None = None,
    ) -> PermissionEntry:
        return await use_cases.set_permission_level(
            self.deps, server_id, xuid, level, actor_id=actor_id
        )

    async def remove_permission(
        self,
        server_id: str,
        xuid: str,
        *,
        actor_id: str | None = None,
    ) -> None:
        await use_cases.remove_permission(self.deps, server_id, xuid, actor_id=actor_id)

    async def list_permissions(self, server_id: str) -> list[PermissionEntry]:
        return await use_cases.list_permissions(self.deps, server_id)

    def register_handlers(self) -> None:
        self._xuid_resolver.register()
