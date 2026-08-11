"""Comandos tipados de los use cases del módulo World (CQRS, §4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True, slots=True)
class CreateWorldCommand:
    """Crea un mundo nuevo (metadata + directorio vacío con ``levelname.txt``).

    Los ajustes opcionales (``seed``/``gamemode``/``difficulty``/
    ``view_distance``) se guardan en la metadata y se inyectan como env al
    activar el mundo. ``None`` = sin configurar (BDS usa sus defaults).
    """

    server_id: str
    name: str
    actor_id: str | None = None
    seed: str | None = None
    gamemode: str | None = None
    difficulty: str | None = None
    view_distance: int | None = None


@dataclass(frozen=True, slots=True)
class ImportWorldCommand:
    """Importa un snapshot (``.mcworld``/tar.gz) como mundo nuevo."""

    server_id: str
    name: str
    stream: BinaryIO
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExportWorldCommand:
    """Exporta un mundo a snapshot (con ``save hold``/``save resume`` si corre)."""

    server_id: str
    name: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class DuplicateWorldCommand:
    """Clona un mundo existente a un nombre nuevo."""

    server_id: str
    source: str
    target: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteWorldCommand:
    """Elimina un mundo (no el activo: el servidor puede estar usándolo)."""

    server_id: str
    name: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class ActivateWorldCommand:
    """Activa un mundo (excluyente por servidor) y publica ``WORLD.ACTIVATED``."""

    server_id: str
    name: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateWorldCommand:
    """Actualiza un mundo: renombra y/o cambia sus ajustes opcionales.

    ``name`` es el nombre actual (clave); ``new_name`` opcional (renombrar el
    directorio + metadata). ``None`` en los ajustes = no cambiar; no se soporta
    "limpiar" un ajuste a ``None`` en esta versión (solo volver a escribirlo).
    """

    server_id: str
    name: str
    actor_id: str | None = None
    new_name: str | None = None
    seed: str | None = None
    gamemode: str | None = None
    difficulty: str | None = None
    view_distance: int | None = None
