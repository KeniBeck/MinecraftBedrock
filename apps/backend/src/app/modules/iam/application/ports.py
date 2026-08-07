"""Puertos de aplicación del módulo IAM (Blueprint §3.1 dependencias).

El dominio no conoce hashing, tokens ni persistencia de sesiones/auditoría; la
aplicación declara estos contratos y la infraestructura los implementa (mismo
patrón que ``ConfigurationReader`` en Server).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.kernel.ports.access import Identity
from app.modules.iam.domain.errors import TokenExpiredError, TokenInvalidError


class PasswordHasher(Protocol):
    """Hashea y verifica contraseñas (argon2id en producción)."""

    def hash(self, password: str) -> str:
        """Devuelve el hash con salt aleatorio embebido."""

    def verify(self, password: str, hashed: str) -> bool:
        """Comprueba la contraseña contra el hash (sin excepciones)."""


class TokenService(Protocol):
    """Emite y valida tokens: access (JWT corto) y refresh (opaco, rotativo)."""

    def create_access_token(self, identity: Identity) -> str:
        """Emite un JWT de corta vida con los claims de la identidad."""

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """Valida el JWT; lanza ``TokenExpiredError``/``TokenInvalidError``."""

    def generate_refresh_token(self) -> str:
        """Genera un refresh token opaco aleatorio (no persistido en claro)."""

    def hash_token(self, raw: str) -> str:
        """Deriva el hash persistible de un token (sha256)."""


@dataclass(frozen=True, slots=True)
class Session:
    """Sesión de refresh (tabla de sesiones, technical-design §15.1)."""

    id: str
    user_id: str
    token_hash: str
    expires_at: datetime
    created_at: datetime
    revoked_at: datetime | None = None
    ip: str | None = None
    ua: str | None = None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class SessionStorePort(Protocol):
    """Persistencia de las sesiones de refresh (revocables)."""

    async def create(self, session: Session) -> None: ...

    async def get_by_token_hash(self, token_hash: str) -> Session | None: ...

    async def revoke(self, session_id: str, at: datetime) -> None: ...


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Registro de auditoría (log básico, sin encadenado: Fase H)."""

    id: str
    actor_id: str | None
    actor_type: str
    action: str
    result: str
    created_at: datetime
    resource_type: str | None = None
    resource_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    ip: str | None = None
    ua: str | None = None


class AuditStorePort(Protocol):
    """Persistencia del audit log (append-only; sin tamper-evidence)."""

    async def record(self, entry: AuditEntry) -> None: ...


# Re-export de errores para consumo de infraestructura (tokens).
__all__ = [
    "AuditEntry",
    "AuditStorePort",
    "PasswordHasher",
    "Session",
    "SessionStorePort",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenService",
]
