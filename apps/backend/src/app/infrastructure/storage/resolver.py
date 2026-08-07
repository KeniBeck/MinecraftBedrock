"""Resolver del ``ServerStoragePort`` por servidor (Fase E paso 12).

Implementa ``ServerStorageResolver`` (puerto de la aplicación World)
reutilizando la lógica de descubrimiento del ``RuntimeSpecFactory``: la raíz
del storage del mundo **coincide** con el directorio que el spec monta como
volumen ``/data`` (sin rutas paralelas, §22).

Cachea la instancia por ``server_id``: los ``asyncio.Lock`` de exclusión
mutua del storage viven en la instancia, y export/duplicado del mismo servidor
deben compartirla (de lo contrario el lock no serviría de nada).
"""

from __future__ import annotations

from app.infrastructure.storage.local import LocalServerStorage
from app.kernel.ports.storage import ServerStoragePort
from app.modules.server.application.spec_factory import RuntimeSpecFactory


class LocalServerStorageResolver:
    """Resuelve y cachea el storage local de cada servidor."""

    def __init__(self, spec_factory: RuntimeSpecFactory) -> None:
        self._spec_factory = spec_factory
        self._cache: dict[str, LocalServerStorage] = {}

    def for_server(self, server_id: str) -> ServerStoragePort:
        storage = self._cache.get(server_id)
        if storage is None:
            storage = LocalServerStorage(self._spec_factory.data_dir(server_id))
            self._cache[server_id] = storage
        return storage
