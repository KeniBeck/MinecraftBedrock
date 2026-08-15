"""Resultados de aplicación del módulo IAM (Bluepring §4.7).

Los DTOs de salida no exponen internos del dominio: ``UserView`` no incluye el
hash de contraseña; ``AuthResult`` solo expone tokens e identidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

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
    email: str | None = None
    avatar: str | None = None


@dataclass(frozen=True, slots=True)
class RoleView:
    """Vista pública de un rol del catálogo base."""

    id: str
    name: str
    description: str
    is_system: bool = True


@dataclass(frozen=True, slots=True)
class AuditLogView:
    """Vista pública de un registro de auditoría (incluye hashes de cadena)."""

    id: str
    actor_id: str | None
    actor_type: str
    action: str
    resource_type: str | None
    resource_id: str | None
    result: str
    detail: dict[str, Any]
    ip: str | None
    ua: str | None
    created_at: datetime | None
    hash: str | None
    prev_hash: str | None


@dataclass(frozen=True, slots=True)
class AuditLogPage:
    """Página de auditoría: registros + total (para paginar)."""

    items: list[AuditLogView]
    total: int


@dataclass(frozen=True, slots=True)
class AuthResult:
    """Resultado de login/refresh: tokens + identidad autenticada."""

    access_token: str
    refresh_token: str
    expires_in: int
    identity: Identity


@dataclass(frozen=True, slots=True)
class TwoFactorEnableResult:
    """Secreto TOTP generado (se muestra una única vez) + backup codes."""

    secret: str
    provisioning_uri: str
    backup_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ApiKeyView:
    """Vista pública de una API key (nunca expone el material)."""

    id: str
    name: str
    scopes: tuple[str, ...]
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ApiKeyCreated:
    """API key creada: vista pública + material (se muestra una única vez)."""

    key: ApiKeyView
    material: str
