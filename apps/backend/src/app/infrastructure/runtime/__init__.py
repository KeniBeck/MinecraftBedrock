"""Adaptadores de runtime (FASE A).

``DockerRuntimeAdapter`` implementa ``ServerRuntimePort`` sobre un único
contenedor Docker; los DTOs normalizados se exponen sin tipos del SDK. La
construcción del cliente Docker queda encapsulada en ``DockerClientFactory``.
"""

from app.infrastructure.runtime.client_factory import (
    DockerClientFactory,
    DockerFromEnvClientFactory,
)
from app.infrastructure.runtime.docker import DockerRuntimeAdapter
from app.infrastructure.runtime.settings import DockerRuntimeSettings
from app.infrastructure.runtime.status import RuntimeInspect, RuntimeStatus

__all__ = [
    "DockerClientFactory",
    "DockerFromEnvClientFactory",
    "DockerRuntimeAdapter",
    "DockerRuntimeSettings",
    "RuntimeInspect",
    "RuntimeStatus",
]
