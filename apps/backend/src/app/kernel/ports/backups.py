"""Contrato ``BackupStorePort`` (Blueprint §4.3, TDD §8.7).

Abstracción del almacenamiento de artefactos de backup. ``ref`` es opaco para
el dominio (la BBDD guarda la referencia); el adaptador resuelve dónde
(disco local, S3 futuro). ``put``/``get`` trabajan con streams.
"""

from __future__ import annotations

from typing import BinaryIO, Protocol


class BackupStorePort(Protocol):
    """Almacena y recupera artefactos de backup bajo referencias estables."""

    def put(self, ref: str, stream: BinaryIO) -> None:
        """Almacena el artefacto bajo la referencia ``ref``."""

    def get(self, ref: str) -> BinaryIO:
        """Abre un stream de lectura del artefacto."""

    def delete(self, ref: str) -> None:
        """Elimina el artefacto."""

    def exists(self, ref: str) -> bool:
        """Comprueba presencia del artefacto."""

    def list(self, location: str | None = None) -> list[str]:
        """Lista artefactos (para prune/retención)."""

    def verify(self, ref: str, expected_checksum: str) -> bool:
        """Recomprueba el checksum del artefacto."""
