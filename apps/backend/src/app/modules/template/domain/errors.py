"""Errores de dominio del módulo Template (Blueprint §4.7, prefijo ``TEMPLATE.*``).

Se traducen a HTTP por el router (misma convención que el resto de módulos):
``TEMPLATE.NOT_FOUND`` → 404, ``TEMPLATE.VALIDATION`` → 422, ``TEMPLATE.CORRUPT``
→ 422 (el artefacto no es un nivel válido), ``TEMPLATE.EXISTS`` → 409 (world de
destino ocupado).
"""

from __future__ import annotations

from typing import Any

from app.kernel.errors import DomainError


class TemplateError(DomainError):
    """Base de errores del módulo Template."""

    code = "TEMPLATE.ERROR"


class TemplateNotFoundError(TemplateError):
    """La plantilla solicitada no existe."""

    code = "TEMPLATE.NOT_FOUND"

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message, context=context)


class TemplateValidationError(TemplateError):
    """Nombre/parámetros de plantilla inválidos."""

    code = "TEMPLATE.VALIDATION"


class TemplateCorruptError(TemplateError):
    """El artefacto no contiene una estructura válida (sin nivel de mundo)."""

    code = "TEMPLATE.CORRUPT"


class TemplateWorldExistsError(TemplateError):
    """El mundo de destino ya ocupa ese nombre en el servidor."""

    code = "TEMPLATE.EXISTS"
