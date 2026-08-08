"""Comandos tipados de los use cases del módulo Template (CQRS, §4.7)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CaptureTemplateCommand:
    """Captura el estado actual de un servidor como plantilla ``.mctemplate``."""

    server_id: str
    name: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class ApplyTemplateCommand:
    """Aplica una plantilla a un servidor (restaura mundo + config capturada)."""

    server_id: str
    template_id: str
    world_name: str | None = None
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteTemplateCommand:
    """Elimina una plantilla (metadata + artefacto)."""

    template_id: str
    actor_id: str | None = None
