"""Entidades del módulo IAM (technical-design §15.1, mínimo viable).

``User`` es el agregado raíz: identidad, credenciales (password hasheado con
argon2id — el hash es opaco para el dominio), estado y roles globales. Las
membresías por servidor se modelan como value objects aparte (``role.py``). Las
sesiones de refresh y el audit log son registros de infraestructura (no
entidades de dominio) en este mínimo viable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.modules.iam.domain.role import BuiltinRole


class UserStatus(StrEnum):
    """Estado de la cuenta (technical-design §15.1)."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


@dataclass(slots=True)
class User:
    """Usuario del panel."""

    id: str
    username: str
    password_hash: str
    display_name: str
    status: UserStatus
    created_at: datetime
    last_login_at: datetime | None = None
    email: str | None = None
    roles: set[BuiltinRole] = field(default_factory=set)
    totp_secret: str | None = None
    totp_enabled: bool = False
    backup_codes: str | None = None
    avatar: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE
