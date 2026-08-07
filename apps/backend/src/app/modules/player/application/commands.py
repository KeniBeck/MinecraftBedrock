"""Comandos tipados de los use cases del módulo Player (CQRS, §4.7)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BanPlayerCommand:
    """Ban a un jugador conocido (por su XUID) vía la facade Console."""

    server_id: str
    xuid: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class UnbanPlayerCommand:
    """Desbaneo de un jugador conocido (por su XUID) vía la facade Console."""

    server_id: str
    xuid: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class KickPlayerCommand:
    """Expulsión de un jugador conocido (por su XUID) vía la facade Console."""

    server_id: str
    xuid: str
    actor_id: str | None = None
