"""Roles y membresías del módulo IAM (Blueprint §3.1, technical-design §15.1).

Roles base fijos del panel (mínimo viable, sin catálogo de permisos por acción:
eso es Fase H). ``BuiltinRole`` define los cuatro roles; ``ROLE_LEVEL`` modela la
jerarquía usada por el RBAC global y el ACL por servidor.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BuiltinRole(StrEnum):
    """Roles base del panel (technical-design §14.2)."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# Jerarquía de privilegio: super_admin(4) > admin(3) > operator(2) > viewer(1).
ROLE_LEVEL: dict[BuiltinRole, int] = {
    BuiltinRole.SUPER_ADMIN: 4,
    BuiltinRole.ADMIN: 3,
    BuiltinRole.OPERATOR: 2,
    BuiltinRole.VIEWER: 1,
}


@dataclass(frozen=True, slots=True)
class Role:
    """Rol del catálogo base (is_system=True para los cuatro base)."""

    name: BuiltinRole
    description: str = ""
    is_system: bool = True


@dataclass(frozen=True, slots=True)
class ServerMembership:
    """Membresía de un usuario sobre un servidor (ACL por servidor).

    ``role`` es el rol efectivo dentro del servidor (mismo catálogo base).
    """

    server_id: str
    user_id: str
    role: BuiltinRole
