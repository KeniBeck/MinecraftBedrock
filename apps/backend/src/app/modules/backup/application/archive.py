"""Formato de artefacto de backup: ``tar`` + ``zstd`` con manifiesto (§8.4).

El artefacto es autodescriptible: un ``tar.zst`` cuyo **primer** miembro es
``manifest.json`` (formato, mundo, entradas del nivel) y cuyo segundo miembro
es ``world.mcworld`` (el zip del árbol del mundo producido por
``ServerStoragePort.world_snapshot``). El SHA-256 del artefacto completo vive
en el registro (BBDD) y se recalcula en streaming — nunca se carga el mundo en
memoria.

Nota (decisión §22): el manifiesto **no** contiene el checksum del propio
artefacto (imposible en una sola pasada de streaming: sería referenciarse a sí
mismo). Lista las entradas del nivel (``level.dat``, ``db/...``) que es lo que
§8.2 usa para validar. Python 3.13 no soporta ``tarfile`` con ``zstd`` nativo
(aún no), así que se envuelve el tar con ``zstandard.ZstdCompressor``.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, BinaryIO, cast

import zstandard

_FORMAT = "bedrockpanel-backup/v1"
_MANIFEST = "manifest.json"
_WORLD_MEMBER = "world.mcworld"


@dataclass(frozen=True, slots=True)
class BackupArchive:
    """Artefacto ya construido (stream + metadatos calculados)."""

    stream: BinaryIO
    size_bytes: int
    checksum: str
    entries: list[str]


def build_backup_archive(world_name: str, world_zip: BinaryIO) -> BackupArchive:
    """Empaqueta el zip del mundo en un ``tar.zst`` con manifiesto al inicio.

    ``world_zip`` debe ser seekable (la ``world_snapshot`` del adaptador local
    lo es: un fichero temporal). Devuelve el artefacto con su checksum SHA-256
    calculado en streaming.
    """
    entries = _zip_entries(world_zip)
    world_size = _size_of(world_zip)

    tmp: BinaryIO = tempfile.TemporaryFile()  # noqa: SIM115 — el caller lo cierra
    try:
        writer = zstandard.ZstdCompressor(threads=-1).stream_writer(tmp)
        with tarfile.open(fileobj=writer, mode="w") as tar:
            _write_manifest_member(tar, world_name, entries)
            world_info = tarfile.TarInfo(_WORLD_MEMBER)
            world_info.size = world_size
            world_zip.seek(0)
            tar.addfile(world_info, world_zip)
        writer.flush(zstandard.FLUSH_FRAME)

        tmp.flush()
        checksum, size = _streaming_sha256(tmp)
        tmp.seek(0)
    except BaseException:
        tmp.close()
        raise

    return BackupArchive(stream=tmp, size_bytes=size, checksum=checksum, entries=entries)


class BackupArchiveReader:
    """Lector de un artefacto: expone manifiesto y zip del mundo por streaming."""

    def __init__(self, archive: BinaryIO) -> None:
        self._tmp: BinaryIO = tempfile.TemporaryFile()  # noqa: SIM115
        try:
            decompressor = zstandard.ZstdDecompressor()
            with decompressor.stream_reader(archive) as source:
                shutil.copyfileobj(source, self._tmp)
            self._tmp.seek(0)
            self._tar = tarfile.open(  # noqa: SIM115 — el reader vive más que este frame (close())
                fileobj=self._tmp, mode="r:"
            )
        except BaseException:
            self._tmp.close()
            raise

    def manifest(self) -> dict[str, Any]:
        member = self._tar.getmember(_MANIFEST)
        raw = self._tar.extractfile(member)
        assert raw is not None
        with raw:
            return cast("dict[str, Any]", json.loads(raw.read().decode("utf-8")))

    def world_zip(self) -> BinaryIO:
        member = self._tar.getmember(_WORLD_MEMBER)
        raw = self._tar.extractfile(member)
        if raw is None:
            raise tarfile.TarError(f"Falta el miembro {_WORLD_MEMBER}")
        return cast(BinaryIO, raw)

    def close(self) -> None:
        self._tar.close()
        self._tmp.close()


def _zip_entries(world_zip: BinaryIO) -> list[str]:
    world_zip.seek(0)
    with zipfile.ZipFile(world_zip) as zf:
        return [info.filename for info in zf.infolist() if not info.is_dir()]


def _size_of(stream: BinaryIO) -> int:
    position = stream.tell()
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(position)
    return size


def _write_manifest_member(tar: tarfile.TarFile, world_name: str, entries: list[str]) -> None:
    manifest = {
        "format": _FORMAT,
        "world": world_name,
        "entries": entries,
        "created_at": datetime.now(UTC).isoformat(),
    }
    payload = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    info = tarfile.TarInfo(_MANIFEST)
    info.size = len(payload)
    tar.addfile(info, io.BytesIO(payload))


def _streaming_sha256(stream: BinaryIO) -> tuple[str, int]:
    hasher = hashlib.sha256()
    stream.seek(0)
    total = 0
    while chunk := stream.read(1024 * 1024):
        hasher.update(chunk)
        total += len(chunk)
    return hasher.hexdigest(), total
