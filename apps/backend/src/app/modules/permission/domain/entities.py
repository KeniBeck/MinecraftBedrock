"""Entidades del dominio Permission (Blueprint §3.6).

``AllowlistEntry`` representa una entrada en ``allowlist.json``.
``PermissionEntry`` representa una entrada en ``permissions.json`` con nivel
``operator``, ``member`` o ``visitor``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PermissionLevel(StrEnum):
    """Niveles de permiso en-juego (Blueprint §3.6)."""

    OPERATOR = "operator"
    MEMBER = "member"
    VISITOR = "visitor"


@dataclass(frozen=True, slots=True)
class AllowlistEntry:
    """Entrada de la allowlist del servidor."""

    name: str
    xuid: str
    ignores_player_limit: bool = False


@dataclass(frozen=True, slots=True)
class PermissionEntry:
    """Entrada de permisos del servidor."""

    xuid: str
    level: PermissionLevel
