"""Errores del dominio Scheduler (códigos ``TASK.*``).

Subtipo de las ramas del kernel con códigos ``TASK.*`` (el blueprint §3.9 y el
ciclo de vida usa ``TASK.*`` tanto para eventos como para errores). Viven en el
módulo para que el kernel no conozca dominios (mismo criterio que Backup/Player).
"""

from __future__ import annotations

from app.kernel.errors import InvalidStateError, NotFoundError, ValidationError


class SchedulerValidationError(ValidationError):
    """Payload/tarea inválida (expresión cron, campos, etc.)."""

    code = "TASK.INVALID_PAYLOAD"


class TaskNotFoundError(NotFoundError):
    """La tarea programada no existe."""

    code = "TASK.NOT_FOUND"


class TaskStateError(InvalidStateError):
    """La tarea está en un estado que impide la operación (p. ej. reactivar)."""

    code = "TASK.INVALID_STATE"
