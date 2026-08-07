"""Contrato ``ServerStoragePort`` (Blueprint §4.2, TDD §6.3).

Abstracción del árbol ``/data`` del servidor como filesystem lógico.
La implementación recomendada (MVP) es ``LocalServerStorage`` en
``infrastructure/storage`` (§22). Toda ruta relativa debe validarse contra
path traversal (``..``, rutas absolutas, symlinks que escapen de la raíz):
es una superficie de seguridad real, con el mismo rigor que
``_validate_runtime_id`` del adaptador Docker.
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

    def move(self, rel_from: str, rel_to: str) -> None:
        """Mueve un fichero/árbol relativo dentro de la raíz (swap atómico).

        El destino no debe existir; el origen sí. Usado por Backup para el
        swap atómico ``staging → worlds/<nombre>`` durante una restauración
        (§8.6). Ambas rutas pasan por la validación de ``_resolve``.
        """

    def list_worlds(self) -> list[dict[str, Any]]:
        """Enumera ``worlds/*`` con tamaño y estructura mínima."""

    def world_snapshot(self, world_name: str) -> BinaryIO:
        """Abre un stream de lectura del árbol de un mundo (formato zip)."""

    def write_snapshot(self, rel: str, stream: BinaryIO) -> None:
        """Restaura un árbol desde un stream (zip ``.mcworld``/tar.gz)."""

    def disk_stats(self) -> dict[str, Any]:
        """Uso/espacio del directorio de datos."""

    async def lock(self, scope: str) -> None:
        """Exclusión mutua en proceso por operación (``scope``).

        ``asyncio.Lock`` por ``scope``: se mantiene a través de ``await``
        (p. ej. export con ``save hold`` en medio). Suficiente para
        single-instance; multi-instancia requeriría un lock distribuido
        (limitación señalada, no resuelta en el MVP).
        """

    async def unlock(self, scope: str) -> None:
        """Libera la exclusión mutua de ``scope``."""
