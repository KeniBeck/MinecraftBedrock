"""Contrato ``ServerRuntimePort`` (Blueprint §4.1, TDD §6.2).

Abstracción del ciclo de vida/proceso de un servidor. El dominio ``Server`` y
``Console`` dependen solo de este puerto; los adaptadores (Docker, Podman,
nativo, k8s) lo implementan en ``infrastructure/runtime``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class RuntimeState(StrEnum):
    """Estado del runtime a nivel infraestructura (Blueprint §4.1)."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DYING = "dying"
    ABSENT = "absent"


class ServerState(StrEnum):
    """Estado del servidor a nivel dominio (Blueprint §16.3)."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"
    REMOVED = "removed"


@dataclass(slots=True)
class RuntimeSpec:
    """Descripción declarativa para materializar un servidor en un runtime.

    Campos según Blueprint §4.1: imagen y tag, ``VERSION``, variables de
    entorno, puertos, volúmenes/montajes, recursos, red, usuario/UID/GID,
    etiquetas, healthcheck y ``stdin_open``/``tty``.
    """

    image: str
    tag: str = "latest"
    version: str = "LATEST"
    environment: dict[str, str] = field(default_factory=dict)
    ports: dict[str, int] = field(default_factory=dict)
    volumes: list[str] = field(default_factory=list)
    resources: dict[str, Any] = field(default_factory=dict)
    network: str | None = None
    user: str | None = None
    labels: dict[str, str] = field(default_factory=dict)
    healthcheck: dict[str, Any] | None = None
    stdin_open: bool = False
    tty: bool = False


class ServerRuntimePort(Protocol):
    """Ejecuta y vigila el proceso de un servidor definido por un ``RuntimeSpec``."""

    def materialize(self, spec: RuntimeSpec) -> str:
        """Crea el artefacto de runtime sin arrancarlo. Devuelve su id interno."""

    def start(self, runtime_id: str) -> None:
        """Arranca el proceso; no espera a que el juego responda."""

    def stop(self, runtime_id: str, grace: int = 30) -> None:
        """Parada ordenada con espera de ``grace``; si no, fuerza."""

    def restart(self, runtime_id: str, grace: int = 30) -> None:
        """Parada ordenada + arranque."""

    def remove(self, runtime_id: str, delete_data: bool = False) -> None:
        """Elimina el artefacto; ``delete_data=False`` conserva el storage."""

    def get_state(self, runtime_id: str) -> RuntimeState:
        """Estado normalizado del runtime."""

    def get_health(self, runtime_id: str) -> dict[str, Any]:
        """Salud del runtime y último cambio de estado."""

    def get_resources(self, runtime_id: str) -> dict[str, Any]:
        """CPU/RAM actuales del proceso."""

    def get_exit_code(self, runtime_id: str) -> int | None:
        """Código de salida del último proceso."""

    def stream_logs(self, runtime_id: str) -> Iterator[bytes]:
        """Stream de líneas stdout/stderr (cola + streaming)."""

    def send_stdin(self, runtime_id: str, data: str) -> None:
        """Escribe en el stdin del proceso (ordenado, con bloqueo por instancia)."""

    def wait_for(self, runtime_id: str, condition: str, timeout: int = 60) -> None:
        """Espera una condición (p. ej. puerto respondiendo, proceso vivo)."""

    def signal(self, runtime_id: str, sig: int) -> None:
        """Señal explícita (SIGTERM/SIGKILL) para casos gestionados."""
