"""Configuración del adaptador Docker (FASE A).

Ajustes cargados desde variables de entorno con prefijo
``BEDROCK_PANEL_DOCKER_`` y defaults tipados. El nombre del contenedor, la
imagen, los volúmenes y los límites salen de aquí: el adaptador no hardcodea
ningún valor.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DockerRuntimeSettings(BaseSettings):
    """Ajustes del contenedor gestionado por ``DockerRuntimeAdapter``."""

    model_config = SettingsConfigDict(
        env_prefix="BEDROCK_PANEL_DOCKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    container_name: str = "bedrock-panel-server"
    image: str = (
        "itzg/minecraft-bedrock-server"
        "@sha256:fd46bd30e7c729eacfeea81bca4a62e7c5957f387f1e377da4d03c66f9a76f3d"
    )
    network: str | None = None
    world_volume: str = "bedrock-panel-worlds"
    data_volume: str = "bedrock-panel-data"
    ports: dict[str, int] = Field(default_factory=dict)
    memory_limit: str | None = None
    cpu_limit: float | None = None
    restart_policy: str = "no"
    docker_timeout: int = 300
