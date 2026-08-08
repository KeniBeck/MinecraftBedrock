"""Entidad del módulo Template (Blueprint §3.11, forma entidad ``Template``).

``Template`` es la metadata de una plantilla de servidor: identidad, nombre,
origen (servidor + mundo del que se capturó), versión de BDS capturada, tamaño
del artefacto ``.mctemplate`` y fechas. El artefacto en sí (zip) vive en el
``TemplateArchiveStore``; esta entidad solo lo describe. El módulo es síncrono
(request/response) y no publica/consume eventos (hallazgo B5 del blueprint).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Template:
    """Metadata de una plantilla ``.mctemplate`` capturada del estado de un server."""

    id: str
    name: str
    version: str
    size_bytes: int
    origin_server_id: str | None
    origin_world: str | None
    created_at: datetime | None
    updated_at: datetime | None
