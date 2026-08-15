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

    def create_temp_token(self, user_id: str) -> str:
        """Emite un JWT de corta vida para completar el segundo factor (2FA)."""

    def decode_temp_token(self, token: str) -> str:
        """Valida el temp token 2FA y devuelve el ``user_id``."""


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
class ApiKey:
    """Clave de API persistida (solo su hash, nunca el material en claro)."""

    id: str
    user_id: str
    name: str
    key_hash: str
    scopes: tuple[str, ...] = ()
    last_used_at: datetime | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None


class ApiKeyStorePort(Protocol):
    """Persistencia de las API keys (hash del material, scopes, rotación)."""

    async def create(self, key: ApiKey) -> None: ...

    async def get_by_hash(self, key_hash: str) -> ApiKey | None: ...

    async def list_for_user(self, user_id: str) -> list[ApiKey]: ...

    async def revoke(self, key_id: str, user_id: str) -> None: ...

    async def rotate(self, key_id: str, user_id: str, key_hash: str) -> None: ...

    async def touch(self, key_id: str, at: datetime) -> None: ...


class SecretCipherPort(Protocol):
    """Cifra secretos sensibles en reposo (Fernet; 2FA/api keys)."""

    def encrypt(self, plaintext: str) -> str:
        """Devuelve el ciphertext (token de Fernet)."""

    def decrypt(self, ciphertext: str) -> str:
        """Devuelve el plaintext; lanza ``SecretCipherError`` si es inválido."""


class TotpServicePort(Protocol):
    """Verifica códigos TOTP y gestiona backup codes (Fase H paso 18)."""

    def generate_secret(self) -> str:
        """Genera un secreto base32 de 32 caracteres (``pyotp.random_base32``)."""

    def provisioning_uri(self, secret: str, username: str) -> str:
        """Devuelve ``otpauth://totp/...`` para el QR."""

    def verify(self, secret: str, code: str) -> bool:
        """Valida un código TOTP con ventana ±1 (``valid_window=1``)."""

    def generate_backup_codes(self) -> tuple[str, ...]:
        """Genera 10 backup codes de 8 caracteres hex (``secrets.token_hex(4)``)."""

    def verify_backup_code(self, code: str, codes: tuple[str, ...]) -> bool:
        """Comprueba si ``code`` está en la lista de backup codes."""


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


@dataclass(frozen=True, slots=True)
class AuditLogRecord:
    """Registro de auditoría con los hashes de la cadena (para consulta)."""

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
    hash: str | None = None
    prev_hash: str | None = None


class AuditStorePort(Protocol):
    """Persistencia del audit log tamper-evident (cadena de hash SHA-256)."""

    async def record(self, entry: AuditEntry) -> None: ...

    async def verify(self) -> list[str]:
        """Verifica la cadena; devuelve errores (vacío = íntegra)."""

    async def list(
        self,
        *,
        actor_id: str | None = None,
        action: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLogRecord], int]:
        """Devuelve ``(registros, total)`` ordenados por fecha descendente."""


# Re-export de errores para consumo de infraestructura (tokens).
__all__ = [
    "AuditEntry",
    "AuditLogRecord",
    "AuditStorePort",
    "PasswordHasher",
    "Session",
    "SessionStorePort",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenService",
]
