"""Eventos de dominio ``CONSOLE.*`` y ``WORLD.SAVED`` (Blueprint §9.1, §9.6).

Console publica ``CONSOLE.COMMAND_SENT`` (acuse) y ``CONSOLE.OUTPUT`` (línea
cruda, sin interpretar negocio). ``WORLD.SAVED`` lo publican los parsers
declarativos de ``infrastructure/parsers`` (detección de línea de guardado,
§7.3); Console no interpreta semántica.
"""

from __future__ import annotations

from typing import Any

from app.kernel.events.event import DomainEvent
from app.modules.console.domain.command import CommandPriority

CONSOLE_COMMAND_SENT = "CONSOLE.COMMAND_SENT"
CONSOLE_OUTPUT = "CONSOLE.OUTPUT"
WORLD_SAVED = "WORLD.SAVED"

CONSOLE_TOPIC_WILDCARD = "console.*"
CONSOLE_OUTPUT_TOPIC = "console.output"
WORLD_SAVED_TOPIC = "world.saved"
TASK_STARTED_TOPIC = "task.started"


def console_command_sent(
    server_id: str,
    command: str,
    priority: CommandPriority,
    *,
    actor_id: str | None = None,
    seq: int | None = None,
) -> DomainEvent:
    """Acuse de un comando escrito en el stdin (Blueprint §9.1)."""
    payload: dict[str, Any] = {"command": command, "priority": priority.value}
    if seq is not None:
        payload["seq"] = seq
    return DomainEvent(
        type=CONSOLE_COMMAND_SENT,
        event_id="",
        server_id=server_id,
        actor_id=actor_id,
        payload=payload,
    )


def console_output(server_id: str, line: str, seq: int) -> DomainEvent:
    """Línea cruda de salida del servidor (sin interpretar)."""
    return DomainEvent(
        type=CONSOLE_OUTPUT,
        event_id="",
        server_id=server_id,
        payload={"line": line, "seq": seq},
    )


def world_saved(server_id: str, line: str) -> DomainEvent:
    """Línea de guardado detectada por un parser declarativo (§7.3)."""
    return DomainEvent(
        type=WORLD_SAVED,
        event_id="",
        server_id=server_id,
        payload={"line": line},
    )
