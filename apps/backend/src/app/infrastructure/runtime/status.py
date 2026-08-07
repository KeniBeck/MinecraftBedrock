"""DTOs normalizados del runtime (FASE A).

Objetos de datos que el adaptador Docker devuelve a los consumidores. Nunca
exponen tipos del Docker SDK: toda la información se convierte aquí a valores
de dominio.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.kernel.ports.runtime import RuntimeState


@dataclass(slots=True)
class RuntimeStatus:
    """Estado observado del contenedor gestionado."""

    running: bool
    healthy: bool | None
    container_id: str
    container_name: str
    image: str
    image_id: str | None
    created_at: str
    started_at: str | None
    status: RuntimeState
    health: str | None
    ports: dict[str, int]
    restart_count: int
    oom_killed: bool


@dataclass(slots=True)
class RuntimeInspect:
    """Inspección completa del contenedor normalizada a dominio."""

    status: RuntimeStatus
    environment: dict[str, str]
    command: list[str]
    memory_limit_bytes: int | None
    cpu_limit_cores: float | None
    restart_policy: str | None
    exit_code: int | None
