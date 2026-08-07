"""Comandos tipados de los use cases del módulo Console (CQRS, §4.7)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.console.domain.command import CommandPriority


@dataclass(frozen=True, slots=True)
class SendCommand:
    """Enviar un comando al stdin del servidor (Blueprint §16.9)."""

    server_id: str
    command: str
    priority: CommandPriority = CommandPriority.NORMAL
    actor_id: str | None = None
