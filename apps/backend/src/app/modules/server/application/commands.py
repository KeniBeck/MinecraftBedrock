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
    """Aplica la config deseada (entrada: evento ``CONFIG.CHANGED``)."""

    server_id: str
    config_rev: int
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class ChangeVersionCommand:
    server_id: str
    version: str
    actor_id: str | None = None
