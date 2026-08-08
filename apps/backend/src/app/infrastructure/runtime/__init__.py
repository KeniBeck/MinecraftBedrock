"""Adaptadores de runtime (FASE A, multi-servidor).

``DockerRuntimeAdapter`` implementa ``ServerRuntimePort`` con un contenedor por
servidor (nombre ``{container_prefix}-{server_id}``, que coincide con el
``runtime_id``); los DTOs normalizados se exponen sin tipos del SDK. La
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
