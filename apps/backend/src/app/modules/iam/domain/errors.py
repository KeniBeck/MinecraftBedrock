"""Errores del módulo IAM (Blueprint §11.1, códigos ``IAM.*``/``AUTH.*``).

Subtipos de las ramas del kernel con códigos de módulo. Viven en el módulo
para que el kernel no conozca dominios (mismo patrón que ``SERVER.*``).
"""

from __future__ import annotations

from app.kernel.errors import BusinessRuleViolation, DomainError, NotFoundError


class IAMError(DomainError):
    """Errores de identidad y acceso (Blueprint §11.1)."""

    code = "IAM.ERROR"


class AuthenticationError(DomainError):
    """Errores de autenticación (credenciales, tokens, estado de cuenta)."""

    code = "AUTH.ERROR"


class AuthorizationError(DomainError):
    """Errores de autorización (RBAC/ACL deniega la acción)."""

    code = "AUTH.FORBIDDEN"


class UserNotFoundError(NotFoundError):
    """El usuario solicitado no existe."""

    code = "IAM.USER_NOT_FOUND"


class UserAlreadyExistsError(BusinessRuleViolation):
    """Intento de crear un usuario con un username ya en uso."""

    code = "IAM.USER_ALREADY_EXISTS"


class RoleNotFoundError(NotFoundError):
    """El rol solicitado no existe en el catálogo base."""

    code = "IAM.ROLE_NOT_FOUND"


class SessionNotFoundError(NotFoundError):
    """La sesión de refresh solicitada no existe."""

    code = "IAM.SESSION_NOT_FOUND"


class InvalidCredentialsError(AuthenticationError):
    """Usuario o contraseña incorrectos (no se distingue cuál)."""

    code = "AUTH.INVALID_CREDENTIALS"


class AccountSuspendedError(AuthenticationError):
    """La cuenta está suspendida y no puede iniciar sesión."""

    code = "AUTH.ACCOUNT_SUSPENDED"


class TokenInvalidError(AuthenticationError):
    """Token (access o refresh) inválido, malformado o no emitido por IAM."""

    code = "AUTH.TOKEN_INVALID"


class TokenExpiredError(AuthenticationError):
    """Token de acceso o refresh vencido."""

    code = "AUTH.TOKEN_EXPIRED"


class TokenRevokedError(AuthenticationError):
    """El refresh token ya fue revocado (logout o rotación previa)."""

    code = "AUTH.TOKEN_REVOKED"


class ForbiddenError(AuthorizationError):
    """La identidad no está autorizada para la acción sobre el recurso."""

    code = "AUTH.FORBIDDEN"
