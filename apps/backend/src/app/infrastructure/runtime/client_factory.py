"""Factoría de clientes Docker (hardening FASE A).

Encapsula la creación del cliente Docker SDK para que
``DockerRuntimeAdapter`` **nunca** cree clientes directamente y solo dependa de
esta abstracción. Permite configurar el endpoint (socket unix, tcp, ssh o
``DOCKER_HOST`` vía entorno) y facilita el mocking y futuras implementaciones
(podman, runtime remoto, etc.).

La factoría traduce sus errores de construcción a excepciones del Kernel;
nunca se propagan ``docker.errors.*`` fuera de Infrastructure.
"""

from __future__ import annotations

from typing import Any, Protocol

import docker
from docker.errors import DockerException

from app.kernel.errors import DockerError


class DockerClientFactory(Protocol):
    """Abstracción de creación del cliente Docker SDK."""

    def create(self) -> Any:
        """Devuelve un cliente Docker SDK listo para usar."""
        ...


class DockerFromEnvClientFactory:
    """Crea clientes Docker desde el entorno o un ``base_url`` explícito.

    - Sin ``base_url``: delega en ``docker.from_env`` (respeta ``DOCKER_HOST``,
      TLS y contexto de la CLI de Docker).
    - Con ``base_url``: construye un cliente apuntando al endpoint indicado
      (``unix://``, ``tcp://``, ``ssh://``).
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: int = 300,
        version: str | None = None,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._version = version

    def create(self) -> Any:
        try:
            if self._base_url is not None:
                return docker.DockerClient(
                    base_url=self._base_url,
                    timeout=self._timeout,
                    version=self._version,
                )
            return docker.from_env(timeout=self._timeout, version=self._version)
        except DockerException as exc:
            if self._has_permission_error(exc):
                raise DockerError(
                    "Permisos insuficientes para acceder al daemon de Docker",
                    context={"base_url": self._base_url, "reason": "permission_denied"},
                ) from exc
            raise DockerError(
                "No se pudo construir el cliente de Docker",
                context={"base_url": self._base_url, "reason": "client_init_failed"},
                retryable=True,
            ) from exc
        except PermissionError as exc:
            raise DockerError(
                "Permisos insuficientes para acceder al daemon de Docker",
                context={"base_url": self._base_url, "reason": "permission_denied"},
            ) from exc
        except OSError as exc:
            raise DockerError(
                "Error de transporte al construir el cliente de Docker",
                context={"base_url": self._base_url, "reason": "transport_error"},
                retryable=True,
            ) from exc

    @staticmethod
    def _has_permission_error(exc: DockerException) -> bool:
        seen: set[int] = set()
        stack: list[BaseException | None] = [exc]
        while stack:
            node = stack.pop()
            if node is None or id(node) in seen:
                continue
            seen.add(id(node))
            if isinstance(node, PermissionError):
                return True
            # ``args`` puede ser una tupla con la causa como 2º elemento, pero la
            # SDK también lo usa como string simple; solo seguimos si es una
            # tupla con un 2º elemento excepción (evita indexar un char y romper).
            if isinstance(node.args, tuple) and len(node.args) > 1:
                link = node.args[1]
                if isinstance(link, BaseException):
                    stack.append(link)
            stack.append(node.__cause__)
            stack.append(node.__context__)
        return False
