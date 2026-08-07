"""Vistas de salida de los use cases del módulo Console (proyecciones, §4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.console.domain.command import CommandPriority
from app.modules.console.domain.console_log import ConsoleLine


@dataclass(frozen=True, slots=True)
class CommandAck:
    """Acuse de envío de un comando (Blueprint §3.8: 'acuses de envío')."""

    server_id: str
    command: str
    priority: CommandPriority
    seq: int
    at: datetime


@dataclass(frozen=True, slots=True)
class BufferView:
    """Proyección del buffer de logs para consumidores."""

    lines: list[ConsoleLine]
    high_water_mark: int
