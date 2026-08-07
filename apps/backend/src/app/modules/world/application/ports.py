"""Puertos de entrada de la aplicación World (Bluepint §3.3, §4.2).

``ServerStorageResolver`` abstrae "dónde está el árbol de datos de un
servidor" para que el módulo World no dependa de la lógica de descubrimiento
del módulo Server (``spec_factory``): la composición raíz implementa el
resolver reutilizando el mismo criterio que el ``RuntimeSpecFactory`` para que
la raíz del storage coincida con el volumen ``/data`` montado (sin rutas
paralelas, §22). El resolver debe **cachear** la instancia por ``server_id``:
los ``asyncio.Lock`` del storage viven en la instancia (exclusión mutua entre
operaciones de export/duplicado del mismo servidor).
"""

from __future__ import annotations

from typing import Protocol

from app.kernel.ports.storage import ServerStoragePort


class ServerStorageResolver(Protocol):
    """Devuelve el ``ServerStoragePort`` del árbol de datos de un servidor."""

    def for_server(self, server_id: str) -> ServerStoragePort:
        """Instancia (cacheada por ``server_id``) del storage del servidor."""
