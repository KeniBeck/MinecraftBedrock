"""Ciclo de vida del stream de logs por servidor (§10 decisión 11, corrección).

Cierra la deuda de la decisión 11: ``ConsoleLogStream`` se exponía en el
``Container`` pero nadie lo arrancaba. Este gestor ataca el mínimo necesario:
``SERVER.STARTED`` lanza una tarea de fondo que consume el stream del servidor
y ``SERVER.STOPPED``/``SERVER.CRASHED``/``SERVER.REMOVED`` la cancelan. Es
wiring/orquestación sobre eventos ya publicados; **no** sustituye al supervisor
de tareas de Fase H.

Multi-stream: una tarea por ``server_id``; ``ConsoleLogStream.consume`` es sin
estado por invocación, así que varios servidores conviven sin cambios en el
adaptador.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.kernel.events.bus import EventBusPort
from app.kernel.events.event import DomainEvent
from app.modules.console.application.ports import ServerConsoleReader
from app.modules.console.infrastructure.stream import ConsoleLogStream

logger = logging.getLogger(__name__)

SERVER_STARTED_TOPIC = "server.started"
SERVER_STOPPED_TOPIC = "server.stopped"
SERVER_CRASHED_TOPIC = "server.crashed"
SERVER_REMOVED_TOPIC = "server.removed"

_STOP_TOPICS = (SERVER_STOPPED_TOPIC, SERVER_CRASHED_TOPIC, SERVER_REMOVED_TOPIC)


class ConsoleStreamManager:
    """Arranca/para la tarea de consumo del stream según el ciclo de vida."""

    def __init__(
        self,
        stream: ConsoleLogStream,
        server: ServerConsoleReader,
        bus: EventBusPort,
    ) -> None:
        self._stream = stream
        self._server = server
        self._bus = bus
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def subscribe(self) -> None:
        """Registra los consumidores de ``SERVER.*`` sobre el bus."""
        self._bus.subscribe(SERVER_STARTED_TOPIC, self._on_server_started)
        for topic in _STOP_TOPICS:
            self._bus.subscribe(topic, self._on_server_stopped)

    def active(self, server_id: str) -> bool:
        """¿Hay una tarea de consumo en curso para el servidor?"""
        task = self._tasks.get(server_id)
        return task is not None and not task.done()

    async def _on_server_started(self, event: DomainEvent) -> None:
        server_id = event.server_id
        if not server_id:
            return
        logger.info("SERVER.STARTED recibido; evaluando arranque del stream de %s", server_id)
        if self.active(server_id):
            logger.info("Stream de %s ya activo; se omite el arranque", server_id)
            return
        server = await self._server.get_server(server_id)
        if server is None or server.runtime_id is None:
            logger.warning("Sin runtime para iniciar el stream de %s", server_id)
            return
        logger.info(
            "Arrancando stream de %s (runtime_id=%s)",
            server_id,
            server.runtime_id,
        )
        self._tasks[server_id] = asyncio.create_task(self._run(server_id, server.runtime_id))

    async def _run(self, server_id: str, runtime_id: str) -> None:
        try:
            await self._stream.consume(server_id, runtime_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — un stream caído no debe tumbar el proceso
            logger.warning("Stream de %s finalizó con error: %s", server_id, exc)
        finally:
            self._tasks.pop(server_id, None)

    async def _on_server_stopped(self, event: DomainEvent) -> None:
        server_id = event.server_id
        if not server_id:
            return
        task = self._tasks.pop(server_id, None)
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
