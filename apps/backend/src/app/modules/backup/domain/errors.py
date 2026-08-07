"""Errores del dominio Backup (Blueprint §11.1).

Subtipo de las ramas del kernel con códigos ``BACKUP.*``. Viven en el módulo
para que el kernel no conozca dominios (mismo criterio que World/Player).
"""

from __future__ import annotations

from app.kernel.errors import NotFoundError, ValidationError


class BackupValidationError(ValidationError):
    """Nombre de mundo inválido o backup no restaurable en su estado actual."""

    code = "BACKUP.INVALID_PAYLOAD"


class BackupNotFoundError(NotFoundError):
    """El registro de backup no existe."""

    code = "BACKUP.NOT_FOUND"


class BackupCorruptError(ValidationError):
    """El artefacto no supera la verificación de integridad (checksum/manifiesto)."""

    code = "BACKUP.CORRUPT"


class BackupInProgressError(ValidationError):
    """Ya hay una operación de backup/restauración en curso para el servidor."""

    code = "BACKUP.IN_PROGRESS"
