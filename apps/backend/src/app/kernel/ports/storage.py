"""Contrato ``ServerStoragePort`` (Blueprint §4.2, TDD §6.3).

Abstracción del árbol ``/data`` del servidor como filesystem lógico.
La implementación recomendada (MVP) es ``LocalStorage`` en
``infrastructure/storage``.
"""

from __future__ import annotations

from typing import Any, BinaryIO, Protocol


class ServerStoragePort(Protocol):
    """Representa el estado persistente (volumen ``/data``) de un servidor."""

    def path(self) -> str:
        """Ruta raíz lógica del storage."""

    def exists(self, rel: str) -> bool:
        """¿Existe el fichero/árbol relativo a la raíz?"""

    def read(self, rel: str) -> bytes:
        """Lee un fichero (ruta relativa, sin path traversal)."""

    def write(self, rel: str, data: bytes) -> None:
        """Escribe un fichero (ruta relativa, sin path traversal)."""

    def remove(self, rel: str) -> None:
        """Elimina un fichero/árbol relativo."""

    def list_worlds(self) -> list[dict[str, Any]]:
        """Enumera ``worlds/*`` con tamaño y estructura mínima."""

    def world_snapshot(self, world_name: str) -> BinaryIO:
        """Abre un stream de lectura del árbol de un mundo."""

    def write_snapshot(self, rel: str, stream: BinaryIO) -> None:
        """Escribe un árbol/archivo desde un stream (restauración)."""

    def disk_stats(self) -> dict[str, Any]:
        """Uso/espacio del directorio de datos."""

    def lock(self, scope: str) -> None:
        """Exclusión mutua por operación (backup/restore)."""

    def unlock(self, scope: str) -> None:
        """Libera la exclusión mutua de ``scope``."""
