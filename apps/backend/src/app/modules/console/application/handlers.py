"""Handlers de eventos consumidos por el módulo Console (Blueprint §3.8).

``TASK.STARTED`` (Scheduler, Fase G) dispara comandos programados. El handler
es defensivo: sin ``server_id`` o sin comandos en el payload no hace nada, y
no falla aunque el Scheduler aún no exista.
"""

from __future__ import annotations

from typing import Any

from app.kernel.events.event import DomainEvent
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.use_cases import SendCommandUseCase


class TaskStartedHandler:
    """``TASK.STARTED`` → comandos programados por servidor (Blueprint §9.6).

    Contrato de payload (Scheduler): ``{"server_id", "commands": [...]}``;
    también acepta un único ``"command"`` como string por compatibilidad.
    """

    def __init__(self, send_command: SendCommandUseCase) -> None:
        self._send_command = send_command

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id or event.payload.get("server_id")
        if not server_id:
            return
        commands = _extract_commands(event.payload)
        if not commands:
            return
        for command in commands:
            if not command.strip():
                continue
            await self._send_command.execute(
                SendCommand(
                    server_id=str(server_id),
                    command=command,
                    actor_id=event.actor_id,
                )
            )


def _extract_commands(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("commands", payload.get("command"))
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str)]
    return []
