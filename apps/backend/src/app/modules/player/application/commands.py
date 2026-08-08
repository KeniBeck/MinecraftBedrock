"""Comandos tipados de los use cases del módulo Player (CQRS, §4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class BanPlayerGloballyCommand:
    """Ban de panel-wide (no atado a un servidor) persistido en el panel."""

    gamertag: str
    xuid: str | None = None
    reason: str | None = None
    expires_at: datetime | None = None
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class UnbanPlayerGloballyCommand:
    """Quitar un ban global persistido (por su ``ban_id``)."""

    ban_id: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class BanPlayerOnServerCommand:
    """Ban por servidor persistido; si el jugador está online, lo expulsa."""

    server_id: str
    player_id: str
    reason: str | None = None
    expires_at: datetime | None = None
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class UnbanPlayerOnServerCommand:
    """Quitar el ban por servidor de un jugador (identificado por su XUID)."""

    server_id: str
    player_id: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class KickPlayerCommand:
    """Expulsión de un jugador conocido (por su XUID) vía la facade Console."""

    server_id: str
    xuid: str
    actor_id: str | None = None
