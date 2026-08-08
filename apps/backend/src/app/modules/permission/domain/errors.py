"""Errores del dominio Permission (Blueprint §11.1).

Subtipo de las ramas del kernel con códigos ``PERMISSION.*``.
"""

from __future__ import annotations

from app.kernel.errors import NotFoundError, ValidationError


class PermissionValidationError(ValidationError):
    """Payload de permiso inválido."""

    code = "PERMISSION.INVALID_PAYLOAD"


class PermissionNotFoundError(NotFoundError):
    """La entrada de permiso/allowlist no existe."""

    code = "PERMISSION.NOT_FOUND"
