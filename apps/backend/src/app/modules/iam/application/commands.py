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
