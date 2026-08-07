"""Adaptador ``LocalBackupStore`` del puerto ``BackupStorePort`` (§4.3, §8.5).

Almacena artefactos de backup en un directorio local (MVP; S3 en Fase 2). Cada
artefacto vive bajo ``{root}/{ref}``; ``ref`` es opaco para el dominio y se
valida contra path traversal. ``put``/``get`` trabajan con streams; ``verify``
recalcula el SHA-256 del artefacto en una sola pasada de streaming.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path, PurePath
from typing import BinaryIO

from app.kernel.errors import BackupStoreError


class LocalBackupStore:
    """``BackupStorePort`` sobre filesystem local (raíz configurable)."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    def put(self, ref: str, stream: BinaryIO) -> None:
        target = self._ref_path(ref)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as out:
            shutil.copyfileobj(stream, out)

    def get(self, ref: str) -> BinaryIO:
        target = self._ref_path(ref)
        if not target.is_file():
            raise BackupStoreError("El artefacto no existe", context={"ref": ref})
        return target.open("rb")

    def delete(self, ref: str) -> None:
        target = self._ref_path(ref)
        if target.exists():
            target.unlink()

    def exists(self, ref: str) -> bool:
        return self._ref_path(ref).is_file()

    def list(self, location: str | None = None) -> list[str]:
        base = self._ref_path(location) if location else self._root
        if not base.is_dir():
            return []
        return [str(path.relative_to(self._root)) for path in base.rglob("*") if path.is_file()]

    def verify(self, ref: str, expected_checksum: str) -> bool:
        target = self._ref_path(ref)
        if not target.is_file():
            return False
        try:
            actual = _sha256_file(target)
        except OSError:
            return False
        return actual == expected_checksum

    # -- validación de referencias ------------------------------------------

    def _ref_path(self, ref: str) -> Path:
        if not isinstance(ref, str) or not ref:
            raise BackupStoreError("Referencia vacía", context={"ref": ref})
        path = PurePath(ref)
        if path.is_absolute() or ".." in path.parts or "\\" in path.as_posix():
            raise BackupStoreError("Referencia de backup inválida", context={"ref": ref})
        return self._root.joinpath(*path.parts)


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()
