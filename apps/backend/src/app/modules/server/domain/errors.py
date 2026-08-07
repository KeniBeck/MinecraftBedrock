"""Errores del dominio Server (Blueprint §10.6, §11.1).

Subtipos de las ramas del kernel con códigos ``SERVER.*``. Viven en el módulo
para que el kernel no conozca dominios.
"""

from __future__ import annotations

from app.kernel.errors import (
    BusinessRuleViolation,
    InvalidStateError,
    NotFoundError,
)


class ServerNotFoundError(NotFoundError):
    """El servidor solicitado no existe (o está eliminado)."""

    code = "SERVER.NOT_FOUND"


class ServerStateError(InvalidStateError):
    """Transición de estado inválida o estado incompatible con la operación."""

    code = "SERVER.INVALID_STATE"


class ServerAlreadyExistsError(BusinessRuleViolation):
    """Intento de crear un servidor con una identidad/name ya en uso."""

    code = "SERVER.ALREADY_EXISTS"


class ServerNotMaterializedError(ServerStateError):
    """Operación de runtime solicitada sin artefacto materializado."""

    code = "SERVER.NOT_MATERIALIZED"


class ServerPortExhaustedError(BusinessRuleViolation):
    """No quedan puertos libres en el pool para el servidor (Blueprint §16.3)."""

    code = "SERVER.PORT_EXHAUSTED"
