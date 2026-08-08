"""Comandos tipados de los use cases del módulo Server (CQRS, Blueprint §4.7)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateServerCommand:
    """Crear una instancia de servidor (Blueprint §6.1)."""

    name: str
    version: str | None = None
    template_id: str | None = None
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class StartServerCommand:
    server_id: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class StopServerCommand:
    server_id: str
    grace: int = 30
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class RestartServerCommand:
    server_id: str
    grace: int = 30
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class RemoveServerCommand:
    server_id: str
    delete_data: bool = False
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class ApplyConfigCommand:
    """Aplica la config deseada (entrada: evento ``CONFIG.CHANGED``/``WORLD.ACTIVATED``).

    ``config_rev`` es opcional: ``None`` significa "reaplicar sin cambiar la
    revisión" (p. ej. ``WORLD.ACTIVATED``, que no conoce las revisions de
    Configuration — decisión §22). ``level_name`` es el directorio del mundo
    activado (el ``name`` de ``WORLD.ACTIVATED``): se inyecta como env
    ``LEVEL_NAME`` al renderizar el spec (decisión §22, ``WORLD.ACTIVATED`` →
    recrear con level-name). ``allow_list`` es el toggle de ``ALLOW_LIST`` del
    evento ``PERMISSION.ALLOWLIST_TOGGLED``: se inyecta como env
    ``ALLOW_LIST=<true/false>`` al renderizar el spec (mismo mecanismo que
    ``LEVEL_NAME``).
    """

    server_id: str
    config_rev: int | None = None
    level_name: str | None = None
    allow_list: bool | None = None
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class ChangeVersionCommand:
    server_id: str
    version: str
    actor_id: str | None = None
