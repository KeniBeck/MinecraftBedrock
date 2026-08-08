"""Puertos de entrada de la aplicación Template (Blueprint §3.11).

``ServerStorageResolver`` abstrae "dónde está el árbol de datos de un servidor"
(reutiliza el mismo criterio estructural que el módulo World, sin acoplar a su
dominio): lo usa Template para leer/restaurar el mundo activo.
``WorldGateway`` da acceso al estado World (mismo criterio que Scheduler inyecta
los facades Server/Backup vía puertos estructurales): Template consulta aquí el
mundo activo (``world_metadata.activated = true``, caminos de §25) en lugar de
leerlo de Configuration. El blueprint §3.11 declara World entre las dependencias
legítimas de Template.
``ConfigurationGateway`` da acceso a la config deseada (lectura para capturar,
escritura para reaplicar al reproducir) sin depender de la entidad Configuration.
``TemplateArchiveWriter`` persiste el artefacto ``.mctemplate`` con el mismo
rigor de path traversal que el storage de World/Backup.
"""

from __future__ import annotations

from typing import Protocol

from app.kernel.ports.storage import ServerStoragePort
from app.modules.configuration.domain.config_profile import ConfigProfile


class ServerStorageResolver(Protocol):
    """Devuelve el ``ServerStoragePort`` del árbol de datos de un servidor."""

    def for_server(self, server_id: str) -> ServerStoragePort:
        """Instancia (cacheada por ``server_id``) del storage del servidor."""


class WorldGateway(Protocol):
    """Superficie de World que Template usa para ubicar el mundo activo."""

    async def active_world(self, server_id: str) -> str | None:
        """Dir de fs (``name``) del mundo activo del servidor, o ``None``."""


class ConfigurationGateway(Protocol):
    """Acceso a la config deseada del servidor (lectura/escritura)."""

    async def get_profile(self, server_id: str) -> ConfigProfile | None:
        """Perfil de config deseada, o ``None`` si aún no existe."""

    async def update_properties(
        self,
        server_id: str,
        properties: dict[str, str],
        *,
        actor_id: str | None = None,
    ) -> ConfigProfile:
        """Valida, persiste (revisión+1) y publica ``CONFIG.CHANGED`` si cambió."""


class TemplateArchiveWriter(Protocol):
    """Persistencia del artefacto ``.mctemplate`` (zip) con validación de ruta."""

    def write(self, template_id: str, data: bytes) -> int:
        """Escribe el artefacto; devuelve el tamaño en bytes."""

    def read(self, template_id: str) -> bytes:
        """Lee el artefacto por id."""

    def exists(self, template_id: str) -> bool:
        """¿Existe el artefacto?"""

    def remove(self, template_id: str) -> None:
        """Elimina el artefacto."""
