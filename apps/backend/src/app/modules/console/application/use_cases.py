"""Use cases del módulo Console (Blueprint §3.8, §16.9).

Console no decide negocio: no valida el contenido del comando, no reacciona a
resultados ni orquesta otros módulos. Solo enruta comandos al runtime del
servidor (vía la cola serializada), mantiene el buffer y sirve suscripciones
de salida. Los parsers viven fuera del núcleo (``infrastructure/parsers``).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.kernel.events.bus import EventBusPort
from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.runtime import ServerRuntimePort, ServerState
from app.kernel.ports.settings import SettingsPort
from app.kernel.time import TimeProviderPort
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.ports import ServerConsoleReader
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.results import BufferView, CommandAck
from app.modules.console.application.streaming import ConsoleOutputRouter, ConsoleSubscription
from app.modules.console.domain.errors import CommandRejectedError, ServerOfflineError
from app.modules.console.domain.repository import ConsoleLogStorePort


@dataclass(slots=True)
class ConsoleDeps:
    """Dependencias comunes de los use cases del módulo Console."""

    server: ServerConsoleReader
    runtime: ServerRuntimePort
    bus: EventBusPort
    time: TimeProviderPort
    settings: SettingsPort
    ids: IdGeneratorPort
    store: ConsoleLogStorePort


class SendCommandUseCase:
    """Envía un comando al stdin del servidor con prioridad (Blueprint §3.8).

    Console no valida el comando; solo comprueba que el servidor exista y esté
    corriendo (identidad/estado de la facade Server) para no escribir sobre un
    proceso sin console disponible.
    """

    def __init__(self, deps: ConsoleDeps, queue: CommandQueue) -> None:
        self._deps = deps
        self._queue = queue

    async def execute(self, cmd: SendCommand) -> CommandAck:
        if not cmd.command or not cmd.command.strip():
            raise CommandRejectedError(
                "Comando vacío",
                context={"server_id": cmd.server_id},
            )
        server = await self._deps.server.get_server(cmd.server_id)
        if server is None:
            raise ServerOfflineError(
                f"Servidor desconocido para la consola: {cmd.server_id}",
                context={"server_id": cmd.server_id},
            )
        if server.state is not ServerState.RUNNING:
            raise ServerOfflineError(
                f"El servidor no está corriendo (estado: {server.state.value})",
                context={"server_id": cmd.server_id, "state": server.state},
            )
        if server.runtime_id is None:
            raise ServerOfflineError(
                f"Servidor sin artefacto de runtime: {cmd.server_id}",
                context={"server_id": cmd.server_id},
            )
        return await self._queue.submit(
            cmd.server_id,
            cmd.command,
            cmd.priority,
            cmd.actor_id,
            server.runtime_id,
        )


class GetBufferUseCase:
    """Consulta el buffer de logs de un servidor (cola + marcador de agua)."""

    def __init__(self, deps: ConsoleDeps) -> None:
        self._deps = deps

    async def execute(self, server_id: str, count: int | None = None) -> BufferView:
        log = await self._deps.store.get(server_id)
        return BufferView(lines=log.tail(count), high_water_mark=log.high_water_mark)


class SubscribeOutputUseCase:
    """Suscripción a la salida en vivo con reanudación idempotente (§16.9)."""

    def __init__(self, deps: ConsoleDeps, router: ConsoleOutputRouter) -> None:
        self._deps = deps
        self._router = router

    async def execute(
        self,
        server_id: str,
        after_seq: int | None = None,
    ) -> ConsoleSubscription:
        return await self._router.subscribe(
            server_id,
            after_seq=after_seq,
            subscriber_id=self._deps.ids.new_id(),
        )
