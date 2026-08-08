"""Store del artefacto ``.mctemplate`` sobre filesystem local.

Reutiliza ``LocalServerStorage`` (raíz ``{storage.base_path}/templates``) para
heredar la **misma validación de path traversal** que aplican World/Backup:
ningún ``template_id`` puede escapar de la raíz. Un artefacto es un único
fichero ``{template_id}.mctemplate`` en ese árbol.
"""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.storage.local import LocalServerStorage
from app.kernel.errors import StorageError
from app.modules.template.application.ports import TemplateArchiveWriter
from app.modules.template.domain.errors import TemplateNotFoundError


class TemplateArchiveStore(TemplateArchiveWriter):
    """Persistencia del artefacto ``.mctemplate`` (zip) con validación de ruta."""

    def __init__(self, root: str | Path) -> None:
        self._store = LocalServerStorage(root)

    def _rel(self, template_id: str) -> str:
        return f"{template_id}.mctemplate"

    def write(self, template_id: str, data: bytes) -> int:
        self._store.write(self._rel(template_id), data)
        return len(data)

    def read(self, template_id: str) -> bytes:
        try:
            return self._store.read(self._rel(template_id))
        except StorageError as exc:
            raise TemplateNotFoundError(
                "El artefacto de la plantilla no existe",
                context={"template_id": template_id},
            ) from exc

    def exists(self, template_id: str) -> bool:
        return self._store.exists(self._rel(template_id))

    def remove(self, template_id: str) -> None:
        self._store.remove(self._rel(template_id))
