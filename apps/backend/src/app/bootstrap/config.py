"""Configuración del panel (Blueprint §10.9).

Config vía variables de entorno con prefijo ``BEDROCK_PANEL_`` y defaults
tipados. Nada de entorno hardcodeado en el código.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes del backend cargados desde entorno/.env."""

    model_config = SettingsConfigDict(
        env_prefix="BEDROCK_PANEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "BedrockPanel"
    app_version: str = "0.1.0"
    debug: bool = False
    api_prefix: str = "/api/v1"
    storage_root: str = "/var/lib/panel/instances"
    log_level: str = "INFO"

    # Persistencia (Fase A paso 2): conexión y pool de Postgres. La URL se
    # sobreescribe con ``BEDROCK_PANEL_DATABASE_URL`` (misma que Alembic).
    database_url: str = "postgresql+psycopg://panel:panel@localhost:5432/panel"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_echo: bool = False

    # Pool de puertos UDP de juego (base; cada instancia usa ``port`` y ``port+1``).
    # Accesible vía ``SettingsPort`` como ``server.port_pool.start`` / ``.end``.
    server_port_pool_start: int = 19132
    server_port_pool_end: int = 19181

    # Pool RCON/SSH (sin solapamiento con juego: el máximo de juego es ``end+1``).
    server_rcon_port_pool_start: int = 25632
    server_rcon_port_pool_end: int = 25681

    # Host/dominio que ven los clientes Bedrock (no el contenedor interno).
    server_public_host: str = "localhost"

    # Monitoring (Fase D paso 9): intervalo del poller y timeout del ping RakNet.
    monitoring_poll_interval_seconds: float = 5.0
    monitoring_probe_timeout: float = 2.0


@lru_cache
def get_settings() -> Settings:
    """Devuelve (y cachea) la configuración del panel."""
    return Settings()
