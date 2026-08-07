"""Puertos de entrada de la aplicación Backup (Blueprint §3.4, §4.3).

``ServerStorageResolver`` replica estructuralmente el del módulo World (misma
forma; Backup no puede importar World, matriz §1.3). ``ServerController``
acota la superficie del módulo Server que Backup necesita (estado + stop/start
para la restauración §8.6): la ``ServerFacade`` lo satisface estructuralmente.
"""

from __future__ import annotations

from typing import Protocol

from app.kernel.ports.storage import ServerStoragePort
from app.modules.server.application.commands import StartServerCommand, StopServerCommand
from app.modules.server.application.results import ServerView


class ServerStorageResolver(Protocol):
    """Devuelve el ``ServerStoragePort`` del árbol de datos de un servidor."""

    def for_server(self, server_id: str) -> ServerStoragePort:
        """Instancia (cacheada por ``server_id``) del storage del servidor."""


class ServerController(Protocol):
    """Superficie de Server que Backup usa durante una restauración (§8.6)."""

    async def get_server(self, server_id: str) -> ServerView | None:
        """Estado actual del servidor."""

    async def stop(self, cmd: StopServerCommand) -> ServerView:
        """Detiene el servidor (parada ordenada síncrona)."""

    async def start(self, cmd: StartServerCommand) -> ServerView:
        """Arranca el servidor."""
