"""Errores del módulo Settings (Blueprint §11.1, códigos ``SETTINGS.*``)."""

from __future__ import annotations

from app.kernel.errors import BusinessRuleViolation, NotFoundError, ValidationError


class SettingNotFoundError(NotFoundError):
    """El ajuste solicitado no existe en el catálogo."""

    code = "SETTINGS.NOT_FOUND"


class SettingValidationError(ValidationError):
    """El valor propuesto no cumple la validación del ajuste."""

    code = "SETTINGS.INVALID_VALUE"


class SettingCategoryError(ValidationError):
    """La categoría solicitada no existe en el catálogo."""

    code = "SETTINGS.INVALID_CATEGORY"


class MaintenanceModeError(BusinessRuleViolation):
    """El panel está en mantenimiento: las operaciones están bloqueadas."""

    code = "SETTINGS.MAINTENANCE_MODE"
