"""Entidad ``ScheduleTask`` (Blueprint §3.9).

Una tarea programada repite una acción sobre un servidor según una expresión
cron. El tipo define el ejecutor (§3.9):

- ``command`` — comando(s) de consola (se publica ``TASK.STARTED``, lo ejecuta
  el ``TaskStartedHandler`` de Console; el payload lleva ``commands``).
- ``backup`` — snapshot de un mundo (``BackupFacade.create_backup``; el payload
  lleva ``world_name``).
- ``restart`` — reinicio del servidor (``ServerFacade.restart``; el payload
  lleva ``grace``).

El estado y el historial de reintentos viven en la entidad: ``failures``
(consecutivos actuales), ``max_retries`` (tope antes de ``FAILED``), y el
backoff se recalcula a partir de ``backoff_seconds``. ``next_run_at`` es la
próxima ocurrencia a evaluar por el reloj/engine; ``last_run_at``/``last_result``
describen la última ejecución.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ScheduleTaskType(StrEnum):
    """Tipo de tarea: define el ejecutor (§3.9)."""

    COMMAND = "command"
    BACKUP = "backup"
    RESTART = "restart"


class ScheduleTaskState(StrEnum):
    """Ciclo de vida de una tarea programada."""

    ACTIVE = "active"
    DISABLED = "disabled"
    RUNNING = "running"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ScheduleTask:
    """Tarea programada recurrente sobre un servidor."""

    id: str
    server_id: str
    name: str
    type: ScheduleTaskType
    cron: str
    payload: dict[str, Any] = field(default_factory=dict)
    state: ScheduleTaskState = ScheduleTaskState.ACTIVE
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_result: str | None = None
    failures: int = 0
    max_retries: int = 3
    backoff_seconds: int = 60
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_due(self) -> bool:
        """La tarea está habilitada y tiene una próxima ejecución prevista."""
        return self.state is ScheduleTaskState.ACTIVE and self.next_run_at is not None
