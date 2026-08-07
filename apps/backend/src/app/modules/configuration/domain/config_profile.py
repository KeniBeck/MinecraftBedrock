"""``ConfigProfile`` y su historial (ADR-004, TDD §15.9, Blueprint §5.4).

``ConfigProfile`` es el estado *deseado* de la config de un servidor
(properties de ``server.properties``) con su revisión; ``applied`` y
``applied_at`` registran la última config confirmada por Server vía
``SERVER.CONFIG_CHANGED`` (detección de pending changes). ``ConfigChange`` es
el historial append-only por servidor (auditoría y rollback, ADR-004).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ConfigProfile:
    """Config deseada de un servidor (properties, versión y revisión)."""

    server_id: str
    properties: dict[str, str]
    version: str
    config_rev: int
    created_at: datetime
    updated_at: datetime
    applied: dict[str, str] | None = None
    applied_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ConfigChange:
    """Entrada append-only del historial de config de un servidor."""

    server_id: str
    config_rev: int
    properties: dict[str, str]
    version: str
    changed_at: datetime
    actor_id: str | None = None
