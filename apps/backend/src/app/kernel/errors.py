"""Taxonomía de errores (Blueprint §10.6 y §11).

Jerarquía única: raíz ``AppError``; ramas ``DomainError``, ``InfrastructureError``,
``HttpError`` y ``UnexpectedError``. Códigos con formato ``MODULO.NOMBRE``.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Raíz de la jerarquía de errores del sistema."""

    code: str = "KERNEL.ERROR"
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        context: dict[str, Any] | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = context or {}
        if code is not None:
            self.code = code
        if retryable is not None:
            self.retryable = retryable


class DomainError(AppError):
    """Errores del dominio: invariantes y reglas de negocio (Blueprint §11.1)."""

    code = "DOMAIN.ERROR"


class ValidationError(DomainError):
    code = "DOMAIN.VALIDATION_ERROR"


class InvalidStateError(DomainError):
    code = "DOMAIN.INVALID_STATE"


class BusinessRuleViolation(DomainError):  # noqa: N818 — nombre definido en Blueprint §11.1
    code = "DOMAIN.RULE_VIOLATION"


class NotFoundError(DomainError):
    code = "DOMAIN.NOT_FOUND"


class ConcurrencyConflictError(DomainError):
    code = "DOMAIN.CONCURRENCY_CONFLICT"


class InfrastructureError(AppError):
    """Errores normalizados de los adaptadores (Blueprint §11.1)."""

    code = "INFRA.ERROR"


class StorageError(InfrastructureError):
    code = "INFRA.STORAGE_ERROR"


class PersistenceError(InfrastructureError):
    code = "INFRA.PERSISTENCE_ERROR"


class RuntimeAdapterError(InfrastructureError):
    code = "INFRA.RUNTIME_ADAPTER_ERROR"


class StatusProbeError(InfrastructureError):
    code = "INFRA.STATUS_PROBE_ERROR"


class BackupStoreError(InfrastructureError):
    code = "INFRA.BACKUP_STORE_ERROR"


class DockerError(RuntimeAdapterError):
    """Errores específicos del adaptador Docker (Blueprint §11.1)."""

    code = "INFRA.DOCKER_ERROR"


class ImageNotFoundError(DockerError):
    code = "DOCKER.IMAGE_NOT_FOUND"


class PortInUseError(DockerError):
    code = "DOCKER.PORT_IN_USE"


class ContainerNotFoundError(DockerError):
    code = "DOCKER.CONTAINER_NOT_FOUND"


class OomKilledError(DockerError):
    code = "DOCKER.OOM_KILLED"


class PullFailedError(DockerError):
    code = "DOCKER.PULL_FAILED"


class ExecFailedError(DockerError):
    code = "DOCKER.EXEC_FAILED"


class DockerTimeoutError(DockerError):
    """Timeout del adaptador Docker.

    El blueprint §11.1 lo nombra ``TimeoutError``; se evita la colisión con el
    builtin ``TimeoutError`` del intérprete.
    """

    code = "DOCKER.TIMEOUT"


class ConsoleError(AppError):
    """Errores de la consola del servidor (Blueprint §11.1)."""

    code = "CONSOLE.ERROR"


class ConsoleBusyError(ConsoleError):
    code = "CONSOLE.BUSY"


class ConsoleUnavailableError(ConsoleError):
    code = "CONSOLE.UNAVAILABLE"


class ServerOfflineError(ConsoleError):
    code = "CONSOLE.SERVER_OFFLINE"


class CommandRejectedError(ConsoleError):
    code = "CONSOLE.COMMAND_REJECTED"


class StdinWriteError(ConsoleError):
    code = "CONSOLE.STDIN_WRITE"


class HttpError(AppError):
    """Errores de presentación (Blueprint §11.1)."""

    code = "HTTP.ERROR"

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        code: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, context=context)
        self.status_code = status_code


class UnexpectedError(AppError):
    """Catch-all: solo se registra en logs con correlation_id (Blueprint §11.1)."""

    code = "KERNEL.UNEXPECTED"
