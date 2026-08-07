"""Entidad ``World`` (Blueprint §3.3, Fase E paso 12).

Un ``World`` es la **metadata** de un mundo dentro del árbol ``worlds/`` del
storage del servidor (la fuente de verdad del contenido es el filesystem vía
``ServerStoragePort``; esta entidad es la caché de metadatos del panel: nombre
del directorio, ``level_name``, tamaño, activación). ``activated`` es
excluyente por servidor: activar un mundo desactiva los demás.
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
