"""Adaptador ``SettingsPort`` basado en entorno (Fase B).

Bridge hacia la configuración del panel mientras el módulo Settings (Fase H)
provee la implementación real. Resolución: env var ``BEDROCK_PANEL_`` +
clave normalizada (``server.image`` → ``BEDROCK_PANEL_SERVER_IMAGE``), después
atributo tipado de ``Settings`` si la clave coincide, después default.
"""

from __future__ import annotations

import os
from typing import Any

from app.bootstrap.config import Settings


class EnvSettingsAdapter:
    """Lee ajustes por clave con prefijo de entorno y defaults."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get(self, key: str, default: Any = None) -> Any:
        env_name = "BEDROCK_PANEL_" + key.upper().replace(".", "_").replace("-", "_")
        if env_name in os.environ:
            return os.environ[env_name]
        attr = key.replace(".", "_").replace("-", "_")
        if hasattr(self._settings, attr):
            return getattr(self._settings, attr)
        if hasattr(self._settings, key):
            return getattr(self._settings, key)
        return default
