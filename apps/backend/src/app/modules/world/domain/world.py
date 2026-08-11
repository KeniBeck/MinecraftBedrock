"""Entidad ``World`` (Blueprint §3.3, Fase E paso 12).

Un ``World`` es la **metadata** de un mundo dentro del árbol ``worlds/`` del
storage del servidor (la fuente de verdad del contenido es el filesystem vía
``ServerStoragePort``; esta entidad es la caché de metadatos del panel: nombre
del directorio, ``level_name``, tamaño, activación y ajustes opcionales).
``activated`` es excluyente por servidor: activar un mundo desactiva los demás.

Los ajustes ``seed``/``gamemode``/``difficulty``/``view_distance`` son
**opcionales** y se inyectan como env al activar el mundo (el ``level-seed``
solo aplica la primera vez que BDS genera el nivel; el resto aplica al mundo
activo vía ``server.properties``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class World:
    """Mundo de un servidor (identidad = ``(server_id, name)``)."""

    id: str
    server_id: str
    name: str
    level_name: str
    size_bytes: int
    activated: bool
    created_at: datetime
    updated_at: datetime
    seed: str | None = None
    gamemode: str | None = None
    difficulty: str | None = None
    view_distance: int | None = None
