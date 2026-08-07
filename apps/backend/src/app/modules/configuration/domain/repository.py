"""Puerto de persistencia del módulo Configuration (Blueprint §3.7, ADR-004).

``ConfigProfile`` (estado deseado) e historial append-only ``ConfigChange``.
La implementación durable es Postgres; en memoria para tests.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.configuration.domain.config_profile import ConfigChange, ConfigProfile


class ConfigurationRepositoryPort(Protocol):
    """Persistencia de ``ConfigProfile`` y su historial."""

    async def get_profile(self, server_id: str) -> ConfigProfile | None: ...

    async def save_profile(self, profile: ConfigProfile) -> None: ...

    async def append_change(self, change: ConfigChange) -> None: ...

    async def history(self, server_id: str, limit: int = 20) -> list[ConfigChange]: ...
