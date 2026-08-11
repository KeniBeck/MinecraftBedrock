"""Adaptador ``LocalServerStorage`` del puerto ``ServerStoragePort`` (§22).

Implementa el árbol ``/data`` de un servidor sobre el filesystem local,
enraizado en ``{storage.base_path}/{server_id}`` (la misma ruta que ya monta
``RuntimeSpecFactory`` como volumen ``/data``, §22 — sin rutas paralelas).

Superficie de seguridad real (mismo rigor que ``_validate_runtime_id`` del
adaptador Docker): **ninguna** operación puede salir de la raíz. ``_resolve``
sanea ``rel`` contra:
  - rutas absolutas,
  - path traversal (``..``) en cualquier componente,
  - symlinks que apunten fuera de la raíz (se detectan resolviendo la ruta y
    verificando que siga bajo la raíz), también en los ``rel`` que aún no
    existen (``resolve(strict=False)`` resuelve los padres existentes).

Los snapshots son streams (un mundo pesa cientos de MB): ``world_snapshot``
empaqueta a zip ``.mcworld`` en un fichero temporal y ``write_snapshot``
extrae zip/tar.gz validando cada miembro (Zip Slip / tar traversal), con
soporte para el directorio envolvente típico de los ``.mcworld``.

Locks: ``asyncio.Lock`` por ``scope`` (exclusión mutua en proceso, suficiente
para single-instance; multi-instancia exigiría un lock distribuido — limitación
señalada, no resuelta en el MVP).
"""

from __future__ import annotations

import asyncio
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePath, PurePosixPath
from typing import Any, BinaryIO

from app.infrastructure.storage.level_reader import (
    read_server_properties_view_distance,
    read_world_settings,
)
from app.kernel.errors import StorageError

_WORLDS = "worlds"


class LocalServerStorage:
    """Storage del servidor sobre filesystem local (raíz = volumen ``/data``)."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._locks: dict[str, asyncio.Lock] = {}

    # -- raíz ---------------------------------------------------------------

    def path(self) -> str:
        return str(self._root)

    # -- operaciones de fichero (con validación estricta) -------------------

    def exists(self, rel: str) -> bool:
        return self._resolve(rel).exists()

    def read(self, rel: str) -> bytes:
        return self._resolve(rel).read_bytes()

    def write(self, rel: str, data: bytes) -> None:
        target = self._resolve(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def remove(self, rel: str) -> None:
        target = self._resolve(rel)
        if not target.exists():
            return
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()

    def move(self, rel_from: str, rel_to: str) -> None:
        """Mueve dentro de la raíz (swap atómico para restauraciones, §22)."""
        source = self._resolve(rel_from)
        target = self._resolve(rel_to)
        if not source.exists():
            raise StorageError(
                "El origen del movimiento no existe en el storage",
                context={"from": rel_from},
            )
        if target.exists():
            raise StorageError(
                "El destino del movimiento ya existe en el storage",
                context={"to": rel_to},
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)

    # -- mundos --------------------------------------------------------------

    def list_worlds(self) -> list[dict[str, Any]]:
        worlds_root = self._resolve(_WORLDS)
        if not worlds_root.is_dir():
            return []
        worlds: list[dict[str, Any]] = []
        for entry in sorted(worlds_root.iterdir()):
            if not entry.is_dir() or not (entry / "level.dat").exists():
                continue
            worlds.append(
                {
                    "name": entry.name,
                    "level_name": _read_level_name(entry),
                    "size_bytes": _tree_size(entry),
                    "modified_at": _iso_mtime(entry),
                }
            )
        return worlds

    def world_settings(self, world_name: str) -> dict[str, Any]:
        """Ajustes del mundo leídos del disco (best effort, dict parcial).

        ``seed``/``gamemode``/``difficulty`` salen del ``level.dat``;
        ``view_distance`` no vive en ``level.dat`` (es ajuste de servidor), así
        que se respalda con el ``view-distance`` de ``server.properties`` de la
        raíz. Nunca lanza: si el nivel no se puede leer, devuelve un dict vacío.
        """
        world_dir = self._resolve(f"{_WORLDS}/{world_name}")
        if not world_dir.is_dir() or not (world_dir / "level.dat").is_file():
            return {}
        settings = read_world_settings(world_dir)
        if "view_distance" not in settings:
            view_distance = read_server_properties_view_distance(self._root)
            if view_distance is not None:
                settings["view_distance"] = view_distance
        return settings

    def world_snapshot(self, world_name: str) -> BinaryIO:
        world_dir = self._resolve(f"{_WORLDS}/{world_name}")
        if not world_dir.is_dir():
            raise StorageError(
                "El mundo no existe en el storage",
                context={"world": world_name},
            )
        fileobj: BinaryIO = tempfile.TemporaryFile()  # noqa: SIM115 — vive más que este frame (el caller lo cierra)
        try:
            with zipfile.ZipFile(fileobj, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                for path in sorted(world_dir.rglob("*")):
                    if path.is_symlink():
                        continue
                    if path.is_file():
                        zf.write(path, arcname=path.relative_to(world_dir).as_posix())
        except BaseException:
            fileobj.close()
            raise
        fileobj.seek(0)
        return fileobj

    def write_snapshot(self, rel: str, stream: BinaryIO) -> None:
        target = self._resolve(rel)
        target.mkdir(parents=True, exist_ok=True)
        magic = stream.read(4)
        stream.seek(0)
        if magic[:2] == b"\x1f\x8b":
            _extract_tar(stream, target)
        elif magic[:2] == b"PK":
            _extract_zip(stream, target)
        else:
            raise StorageError(
                "Formato de snapshot no soportado (esperado .mcworld/zip o tar.gz)",
                context={"rel": rel, "magic": magic.hex()},
            )

    def disk_stats(self) -> dict[str, Any]:
        self._root.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(self._root)
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "root_bytes": _tree_size(self._root),
        }

    # -- exclusión mutua en proceso -----------------------------------------

    async def lock(self, scope: str) -> None:
        lock = self._locks.setdefault(scope, asyncio.Lock())
        await lock.acquire()

    async def unlock(self, scope: str) -> None:
        lock = self._locks.get(scope)
        if lock is not None and lock.locked():
            lock.release()

    # -- validación de rutas --------------------------------------------------

    def _resolve(self, rel: str) -> Path:
        """Resuelve ``rel`` bajo la raíz, rechazando cualquier escape."""
        if not isinstance(rel, str) or not rel:
            raise StorageError("Ruta relativa vacía", context={"rel": rel})
        path = PurePath(rel)
        if path.is_absolute():
            raise StorageError(
                "Ruta absoluta no permitida en el storage",
                context={"rel": rel},
            )
        if "\\" in rel:
            raise StorageError(
                "Separador de Windows no permitido en el storage",
                context={"rel": rel},
            )
        if any(part.endswith(":") for part in path.parts):
            raise StorageError(
                "Ruta con unidad de Windows (p. ej. 'C:') no permitida",
                context={"rel": rel},
            )
        if ".." in path.parts:
            raise StorageError(
                "Path traversal no permitido en el storage",
                context={"rel": rel},
            )
        candidate = self._root / path
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self._root):
            raise StorageError(
                "La ruta resuelve fuera de la raíz del storage (symlink/salto)",
                context={"rel": rel, "resolved": str(resolved)},
            )
        return resolved


def _read_level_name(world_dir: Path) -> str:
    levelname = world_dir / "levelname.txt"
    if levelname.is_file():
        return levelname.read_text(encoding="utf-8", errors="replace").strip()
    return world_dir.name


def _tree_size(root: Path) -> int:
    if root.is_file():
        return root.stat().st_size
    total = 0
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total


def _iso_mtime(path: Path) -> str:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return ""
    return str(int(mtime))


def _safe_arcname(name: str) -> PurePosixPath:
    """Valida un miembro de zip/tar contra Zip Slip y devuelve la ruta limpia."""
    if not isinstance(name, str) or not name:
        raise StorageError("Miembro de snapshot con nombre vacío", context={"member": name})
    path = PurePosixPath(name)
    if path.is_absolute():
        raise StorageError("Miembro de snapshot con ruta absoluta", context={"member": name})
    if ".." in path.parts:
        raise StorageError("Miembro de snapshot con path traversal", context={"member": name})
    if not path.parts:
        raise StorageError("Miembro de snapshot vacío", context={"member": name})
    return path


def _strip_wrapper(paths: list[PurePosixPath]) -> PurePosixPath | None:
    """Devuelve el directorio envolvente común si todos los miembros lo comparten."""
    firsts = {parts.parts[0] for parts in paths if parts}
    if len(firsts) == 1 and all(len(parts.parts) >= 2 for parts in paths):
        return PurePosixPath(firsts.pop())
    return None


def _extract_zip(stream: BinaryIO, target: Path) -> None:
    with zipfile.ZipFile(stream) as zf:
        paths = [_safe_arcname(info.filename) for info in zf.infolist()]
        wrapper = _strip_wrapper(paths)
        for info, path in zip(zf.infolist(), paths, strict=True):
            if wrapper is not None and path.parts[0] == wrapper.name:
                parts = path.parts[1:]
            else:
                parts = path.parts
            if not parts:
                continue
            dest = target.joinpath(*parts)
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)


def _extract_tar(stream: BinaryIO, target: Path) -> None:
    with tarfile.open(fileobj=stream, mode="r:gz") as tf:
        members = tf.getmembers()
        paths = [_safe_arcname(member.name) for member in members]
        wrapper = _strip_wrapper(paths)
        for member, path in zip(members, paths, strict=True):
            if member.issym() or member.islnk():
                raise StorageError(
                    "Snapshot tar con symlink/hardlink no permitido",
                    context={"member": member.name},
                )
            if wrapper is not None and path.parts[0] == wrapper.name:
                parts = path.parts[1:]
            else:
                parts = path.parts
            if not parts:
                continue
            dest = target.joinpath(*parts)
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            source = tf.extractfile(member)
            if source is None:
                continue
            with source, dest.open("wb") as out:
                shutil.copyfileobj(source, out)
