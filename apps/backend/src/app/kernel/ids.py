"""Puerto ``IdGeneratorPort`` (Blueprint §1.2, TDD §16 kernel).

Generación de IDs por defecto UUID v7. La implementación concreta se registra
en el bootstrap; los dominios solo dependen de esta interfaz.
"""

from __future__ import annotations

from typing import Protocol


class IdGeneratorPort(Protocol):
    """Genera identificadores únicos (UUID v7)."""

    def new_id(self) -> str:
        """Devuelve un nuevo identificador único."""

    def new_id_bytes(self) -> bytes:
        """Devuelve un nuevo identificador en formato binario (16 bytes)."""
