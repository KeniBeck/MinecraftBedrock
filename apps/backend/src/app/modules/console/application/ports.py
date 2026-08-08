"""Puertos de aplicación del módulo Console (Blueprint §3.8).

Console depende de la facade Server **solo en modo lectura** (identidad y
estado del proceso) para enrutar comandos al runtime correcto y rechazar
escrituras sobre servidores no disponibles. Nunca modifica el módulo Server.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.server.application.results import ServerView


class ServerConsoleReader(Protocol):
    """Vista de solo lectura de identidad/estado de un servidor (facade Server)."""

    async def get_server(self, server_id: str) -> ServerView | None:
        """Devuelve la proyección del servidor o ``None`` si no existe."""

    async def list_servers(self) -> list[ServerView]:
        """Devuelve la proyección de todos los servidores (lectura)."""
