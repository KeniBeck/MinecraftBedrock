"""Errores del dominio World (Blueprint §11.1).

Subtipo de las ramas del kernel con códigos ``WORLD.*``. Viven en el módulo
para que el kernel no conozca dominios (mismo criterio que Server/Player).
"""

from __future__ import annotations

from app.kernel.errors import NotFoundError, ValidationError


class WorldValidationError(ValidationError):
    """Nombre de mundo inválido (vacío, con separadores, ``..``, oculto)."""

    code = "WORLD.INVALID_PAYLOAD"


class WorldNotFoundError(NotFoundError):
    """El mundo no existe en el storage/metadata del servidor."""

    code = "WORLD.NOT_FOUND"


class WorldAlreadyExistsError(ValidationError):
    """Ya existe un mundo con ese nombre en el servidor."""

    code = "WORLD.ALREADY_EXISTS"


class WorldCorruptError(ValidationError):
    """El snapshot/mundo importado no tiene ``level.dat`` (nivel inválido)."""

    code = "WORLD.CORRUPT"


class WorldActiveError(ValidationError):
    """El mundo activo no se puede eliminar (el servidor corre con él)."""

    code = "WORLD.ACTIVE_IN_USE"
