"""Puertos de aplicación del módulo Server (Blueprint §3.2, §3.7, §16.8).

El módulo Server depende de la facade Configuration **solo en modo lectura**
para obtener la config deseada (propiedades → env ya mapeado) y su revisión.
Aplicar cambios nunca invoca a Configuration: entra por evento ``CONFIG.CHANGED``
(Blueprint §3.2 dependencias permitidas).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DesiredConfig:
    """Config deseada leída de la facade Configuration (solo lectura)."""

    version: str
    environment: dict[str, str] = field(default_factory=dict)
    config_rev: int = 0


class ConfigurationReader(Protocol):
    """Vista de solo lectura de la config deseada (facade Configuration)."""

    async def desired_config(self, server_id: str) -> DesiredConfig: ...


class TemplateReader(Protocol):
    """Vista de solo lectura de plantillas (facade Template, opcional en creación)."""

    async def default_template(self) -> str | None: ...
