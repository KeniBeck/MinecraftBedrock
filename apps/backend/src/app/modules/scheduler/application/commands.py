"""Comandos tipados de los use cases del módulo Scheduler (CQRS, Blueprint §4.7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CreateTaskCommand:
    """Crear una tarea programada recurrente (expresión cron)."""

    server_id: str
    name: str
    type: str
    cron: str
    payload: dict[str, Any] = field(default_factory=dict)
    max_retries: int = 3
    backoff_seconds: int = 60
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateTaskCommand:
    """Edita los campos editables de una tarea existente (los que vienen seteados)."""

    task_id: str
    name: str | None = None
    cron: str | None = None
    payload: dict[str, Any] | None = None
    max_retries: int | None = None
    backoff_seconds: int | None = None
    state: str | None = None
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteTaskCommand:
    """Elimina una tarea programada."""

    task_id: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class RunTaskCommand:
    """Ejecuta una tarea ahora (manual o vía engine), con reintentos de por medio."""

    task_id: str
    actor_id: str | None = None
