"""Reconciliación de streams de Console al arrancar el panel.

Tras un restart del backend los streams de los servidores que ya estaban
``running`` dejan de capturar líneas nuevas (BDS las sigue emitiendo pero no hay
consumidor). Este reconciler, ejecutado al inicio del lifespan, consulta los
servidores con estado persistido ``running`` y arranca su stream — sin confiar
ciegamente en el estado guardado: verifica contra el runtime real que el
contenedor sigue corriendo y solo entonces arranca (mismo efecto que un
``SERVER.STARTED`` recién llegado).

Si el contenedor real ya no corre, no fuerza nada aquí: el ``StatusPoller`` del
Monitoreo lo reconcilia en su próximo ciclo (evita condiciones de carrera entre
esta reconciliación y el poller).
"""

from __future__ import annotations

import logging

from app.kernel.ports.runtime import RuntimeState, ServerRuntimePort, ServerState
from app.modules.console.application.ports import ServerConsoleReader
from app.modules.console.infrastructure.stream_manager import ConsoleStreamManager

logger = logging.getLogger(__name__)


class ConsoleStreamReconciler:
    """Arranca los streams de servidores ``running`` que sobreviven un restart."""

    def __init__(
        self,
        manager: ConsoleStreamManager,
        server: ServerConsoleReader,
        runtime: ServerRuntimePort,
    ) -> None:
        self._manager = manager
        self._server = server
        self._runtime = runtime

    async def reconcile(self) -> None:
        """Arranca streams de los servidores con estado ``running`` real."""
        for server in await self._server.list_servers():
            if server.state is not ServerState.RUNNING:
                continue
            if server.runtime_id is None:
                logger.warning("Server running sin runtime_id; se omite: %s", server.id)
                continue
            if self._runtime.get_state(server.runtime_id) is not RuntimeState.RUNNING:
                logger.info(
                    "Server %s persistido running pero contenedor no corre; "
                    "lo reconcilia el poller",
                    server.id,
                )
                continue
            logger.info("Reconciliando stream del servidor running %s", server.id)
            await self._manager.ensure_stream(server.id)
