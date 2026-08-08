"""Configuración del adaptador Docker (FASE A, multi-servidor).

Ajustes cargados desde variables de entorno con prefijo
``BEDROCK_PANEL_DOCKER_`` y defaults tipados. Con la generalización a N
servidores, el adaptador ya no gestiona "un contenedor" fijo: cada servidor
tiene su propio contenedor cuyo nombre se deriva del ``server_id``
(``{container_prefix}-{server_id}``). La imagen, puertos, volúmenes, recursos y
restart policy vienen por servidor desde el ``RuntimeSpec`` (``RuntimeSpecFactory``);
aquí solo queda el prefijo de nombres y el timeout del cliente.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class DockerRuntimeSettings(BaseSettings):
    """Ajustes del adaptador Docker multi-servidor.

    Ya no describe un contenedor concreto: ``container_prefix`` se combina con
    el ``server_id`` de cada ``RuntimeSpec`` para producir el nombre real por
    servidor (``{prefix}-{server_id}``). El resto de propiedades del contenedor
    (imagen, puertos, volúmenes, recursos, restart) llega por ``RuntimeSpec``.
    """

    model_config = SettingsConfigDict(
        env_prefix="BEDROCK_PANEL_DOCKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    container_prefix: str = "bedrock-panel"
    docker_timeout: int = 300
