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

    # Importación de mundos (paso de cierre §16): tamaño máximo de un snapshot
    # ``.mcworld``/tar.gz subido por multipart. Starlette spolea los archivos a
    # disco y su ``max_part_size`` solo limita campos, así que el límite real se
    # valida aquí al leer el ``UploadFile`` (los mundos pesan cientos de MB).
    world_max_import_bytes: int = 2 * 1024 * 1024 * 1024

    # Monitoring (Fase D paso 9): intervalo del poller y timeout del ping RakNet.
    monitoring_poll_interval_seconds: float = 5.0
    monitoring_probe_timeout: float = 2.0

    # Scheduler (Fase G paso 15): intervalo del reloj, ventana para reconciliar
    # fallos de backup y backoff mínimo de la política de reinicio tras crash.
    scheduler_poll_interval_seconds: float = 5.0
    scheduler_reconcile_window_seconds: float = 30.0
    scheduler_crash_retry_seconds: float = 60.0

    # Notification (Fase H paso 17): cuotas del gateway WebSocket.
    notification_rate_per_second: float = 100.0
    notification_burst: int = 100
    notification_resume_limit: int = 1000

    # IAM completo (Fase H paso 18): clave Fernet para secretos 2FA/backup codes,
    # issuer del provisioning URI y TTL del temp token del segundo factor.
    iam_encryption_key: str = "9Dfa2Y5t4kMX6k4oyar_EgtQ1cFcdPE8V_6I688Tu4k="
    iam_totp_issuer: str = "BedrockPanel"
    iam_temp_token_ttl_seconds: int = 300

    # Clave HMAC de firma de los JWT de acceso (HS256). Si no se define su
    # fallback de desarrollo es "dev-insecure-secret-change-me" (29 bytes), por
    # lo que PyJWT emite un InsecureKeyLengthWarning (<32). En producción se
    # recomienda una cadena larga, p. ej. `secrets.token_urlsafe(48)`.
    iam_jwt_secret: str = "dev-insecure-secret-change-me"

    # Bootstrap de administrador inicial (producción): si se definen usuario y
    # contraseña, el backend crea en el arranque un super_admin con esos
    # credenciales (idempotente; no sobrescribe si ya existe). Vacío = desactivado.
    bootstrap_admin_username: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_display_name: str = "Administrador"


@lru_cache
def get_settings() -> Settings:
    """Devuelve (y cachea) la configuración del panel."""
    return Settings()
