"""Entidades de ban del módulo Player (bounded context §5.2, agregados §5.1).

``GlobalBan`` es un ban no atado a un servidor (decisión panel-wide) y
``ServerBan`` un ban por servidor; ambos son agregados distintos de ``Player``.
En modo offline/LAN el XUID suele venir en ``0`` o no confiable, por lo que el
matching hace fallback a ``gamertag`` (case-insensitive): un "ban blando" de
disuasión, no seguridad real (ADR-011).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class BanScope(StrEnum):
    """Alcance de un ban (payload de ``PLAYER.BANNED``/``PLAYER.UNBANNED``)."""

    GLOBAL = "global"
    SERVER = "server"


def normalize_gamertag(gamertag: str) -> str:
    """Gamertag normalizado (lower-case) usado como clave de unicidad."""
    return gamertag.strip().lower()


def is_valid_xuid(xuid: str | None) -> bool:
    """Un XUID es fiable solo si no es vacío ni el placeholder ``0`` offline."""
    return bool(xuid and xuid.strip() and xuid.strip() != "0")


def kick_command(gamertag: str, reason: str | None) -> str:
    """Comando ``kick <gamertag> [reason]`` para BDS vía Console."""
    if reason:
        return f"kick {gamertag} {reason}"
    return f"kick {gamertag}"


@dataclass(frozen=True, slots=True)
class GlobalBan:
    """Ban de panel-wide: no pertenece a un servidor."""

    id: str
    gamertag: str
    banned_by: str
    created_at: datetime
    xuid: str | None = None
    reason: str | None = None
    expires_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        """Vigente si no expira o la expiración es futura."""
        return self.expires_at is None or self.expires_at > now


@dataclass(frozen=True, slots=True)
class ServerBan:
    """Ban por servidor (atado a ``server_id``)."""

    id: str
    server_id: str
    gamertag: str
    banned_by: str
    created_at: datetime
    xuid: str | None = None
    reason: str | None = None
    expires_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        """Vigente si no expira o la expiración es futura."""
        return self.expires_at is None or self.expires_at > now
