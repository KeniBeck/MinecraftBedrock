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
class ConsoleObservation:
    """Comando enviado + líneas de salida observadas en la ventana posterior.

    ``send_command`` solo confirma la escritura en stdin (acuse), no el resultado
    del comando. Para comandos cuyo resultado importa (p. ej. el ``kick``), esta
    vista añade las líneas de consola que llegan en los ``window_s`` siguientes:
    el llamador decide si indican éxito o error (Console no interpreta negocio).
    """

    ack: CommandAck
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BufferView:
    """Proyección del buffer de logs para consumidores."""

    lines: list[ConsoleLine]
    high_water_mark: int
