"""Facade pública del módulo Console (Blueprint §3.8: enviar comando con
prioridad, suscribirse a salida, obtener buffer). Los consumidores usan esta
facade, nunca el dominio directo.
"""

from __future__ import annotations

from app.modules.console.application.commands import SendCommand
from app.modules.console.application.handlers import TaskStartedHandler
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.results import BufferView, CommandAck
from app.modules.console.application.streaming import (
    ConsoleOutputRouter,
    ConsoleSubscription,
)
from app.modules.console.application.use_cases import (
    ConsoleDeps,
    GetBufferUseCase,
    SendCommandUseCase,
    SubscribeOutputUseCase,
)
from app.modules.console.domain.events import CONSOLE_OUTPUT_TOPIC, TASK_STARTED_TOPIC


class ConsoleFacade:
    """Puerta de entrada única al módulo Console (adapter-driven)."""

    def __init__(
        self,
        deps: ConsoleDeps,
        queue: CommandQueue,
        router: ConsoleOutputRouter,
    ) -> None:
        self.deps = deps
        self._send = SendCommandUseCase(deps, queue)
        self._get_buffer = GetBufferUseCase(deps)
        self._subscribe = SubscribeOutputUseCase(deps, router)
        self._router = router

    async def send_command(self, cmd: SendCommand) -> CommandAck:
        return await self._send.execute(cmd)

    async def get_buffer(self, server_id: str, count: int | None = None) -> BufferView:
        return await self._get_buffer.execute(server_id, count=count)

    async def subscribe(
        self,
        server_id: str,
        after_seq: int | None = None,
    ) -> ConsoleSubscription:
        return await self._subscribe.execute(server_id, after_seq=after_seq)

    def register_handlers(self) -> None:
        """Suscriptores del módulo sobre el bus (Blueprint §3.8)."""
        self.deps.bus.subscribe(TASK_STARTED_TOPIC, TaskStartedHandler(self._send))
        self.deps.bus.subscribe(CONSOLE_OUTPUT_TOPIC, self._router.on_output)
