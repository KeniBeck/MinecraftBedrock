"""Comandos de aplicación del módulo IAM (Bluepring §4.7).

``actor_id`` identifica quién ejecuta la operación (autorización en
Presentación, fuera de este paso); los comandos de autenticación no lo llevan
porque aún no hay identidad.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.iam.domain.role import BuiltinRole


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    """Admin crea un usuario."""

    username: str
    password: str
    display_name: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class LoginCommand:
    """Login con credenciales (usuario + contraseña)."""

    username: str
    password: str
    ip: str | None = None
    ua: str | None = None


@dataclass(frozen=True, slots=True)
class LoginCredentials:
    """Credenciales crudas que consume ``AccessControlPort.authenticate``."""

    username: str
    password: str
    ip: str | None = None
    ua: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshCommand:
    """Rota el refresh token y emite un nuevo access token."""

    refresh_token: str
    ip: str | None = None
    ua: str | None = None


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    """Revoca la sesión asociada al refresh token."""

    refresh_token: str


@dataclass(frozen=True, slots=True)
class AssignRoleCommand:
    """Admin concede un rol global a un usuario."""

    user_id: str
    role: BuiltinRole
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class AssignMembershipCommand:
    """Admin concede/actualiza la membresía de un usuario sobre un servidor."""

    user_id: str
    server_id: str
    role: BuiltinRole
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateUserCommand:
    """Admin actualiza campos parciales de un usuario (no username/password)."""

    user_id: str
    display_name: str | None = None
    email: str | None = None
    status: str | None = None
    roles: tuple[BuiltinRole, ...] | None = None
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteUserCommand:
    """Admin suspende un usuario (soft delete; preserva auditoría)."""

    user_id: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class EnableTwoFactorCommand:
    """Inicia la habilitación de 2FA (genera secreto + backup codes)."""

    user_id: str


@dataclass(frozen=True, slots=True)
class ConfirmTwoFactorCommand:
    """Confirma la habilitación verificando el código TOTP generado."""

    user_id: str
    code: str


@dataclass(frozen=True, slots=True)
class VerifyTwoFactorLoginCommand:
    """Completa el login tras validar el segundo factor (temp token + código)."""

    temp_token: str
    code: str
    ip: str | None = None
    ua: str | None = None


@dataclass(frozen=True, slots=True)
class RegenerateBackupCodesCommand:
    """Regenera los backup codes (requiere 2FA ya verificado)."""

    user_id: str


@dataclass(frozen=True, slots=True)
class DisableTwoFactorCommand:
    """Desactiva el 2FA (limpia secreto + backup codes + flag)."""

    user_id: str


@dataclass(frozen=True, slots=True)
class CreateApiKeyCommand:
    """Crea una API key para el usuario con un set de scopes."""

    user_id: str
    name: str
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RevokeApiKeyCommand:
    """Revoca la API key del usuario."""

    user_id: str
    key_id: str


@dataclass(frozen=True, slots=True)
class RotateApiKeyCommand:
    """Rota el material de la API key (nuevo hash, mismo id/scopes)."""

    user_id: str
    key_id: str
