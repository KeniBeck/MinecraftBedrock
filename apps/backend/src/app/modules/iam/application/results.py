"""Resultados de aplicación del módulo IAM (Bluepring §4.7).

Los DTOs de salida no exponen internos del dominio: ``UserView`` no incluye el
hash de contraseña; ``AuthResult`` solo expone tokens e identidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.kernel.ports.access import Identity


@dataclass(frozen=True, slots=True)
class UserView:
    """Vista pública de un usuario."""

    id: str
    username: str
    display_name: str
    status: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    created_at: datetime | None = None
    last_login_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuthResult:
    """Resultado de login/refresh: tokens + identidad autenticada."""

    access_token: str
    refresh_token: str
    expires_in: int
    identity: Identity
