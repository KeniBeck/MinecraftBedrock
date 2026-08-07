"""Repositorio de Configuration en memoria (tests y MVP sin BBDD)."""

from __future__ import annotations

from app.modules.configuration.domain.config_profile import ConfigChange, ConfigProfile


class InMemoryConfigurationRepository:
    """``ConfigurationRepositoryPort`` en memoria."""

    def __init__(self) -> None:
        self._profiles: dict[str, ConfigProfile] = {}
        self._history: dict[str, list[ConfigChange]] = {}

    async def get_profile(self, server_id: str) -> ConfigProfile | None:
        return self._profiles.get(server_id)

    async def save_profile(self, profile: ConfigProfile) -> None:
        self._profiles[profile.server_id] = profile

    async def append_change(self, change: ConfigChange) -> None:
        self._history.setdefault(change.server_id, []).append(change)

    async def history(self, server_id: str, limit: int = 20) -> list[ConfigChange]:
        return self._history.get(server_id, [])[-limit:]
