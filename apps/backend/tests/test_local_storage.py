"""Tests de seguridad y comportamiento de ``LocalServerStorage`` (§22).

La validación de rutas es la pieza más fácil de dejar con un agujero de
seguridad; aquí se prueba a fondo: path traversal (``..`` en cualquier
posición), rutas absolutas, symlinks que escapan de la raíz, y que las
operaciones de snapshot/restauración (Zip Slip / tar traversal) tampoco
pueden escribir fuera de la raíz.
"""

from __future__ import annotations

import io
import os
import tarfile
import zipfile
from pathlib import Path

import pytest

from app.infrastructure.storage.local import LocalServerStorage
from app.kernel.errors import StorageError

RADIUS = "radicchio"


@pytest.fixture
def storage(tmp_path: Path) -> LocalServerStorage:
    root = tmp_path / "server-data"
    root.mkdir()
    return LocalServerStorage(root)


@pytest.fixture
def storage_with_world(tmp_path: Path) -> LocalServerStorage:
    root = tmp_path / "server-data"
    root.mkdir()
    storage = LocalServerStorage(root)
    storage.write("worlds/Alpha/level.dat", b"\x0a\x00\x00")
    storage.write("worlds/Alpha/levelname.txt", b"Alpha")
    storage.write("worlds/Alpha/db/1.lbd", b"chunk")
    return storage


# -- operaciones básicas -----------------------------------------------------


def test_write_read_remove_existen_dentro_de_la_raiz(storage: LocalServerStorage) -> None:
    storage.write("worlds/Alpha/level.dat", b"\x0a\x00\x00")
    assert storage.exists("worlds/Alpha/level.dat")
    assert storage.read("worlds/Alpha/level.dat") == b"\x0a\x00\x00"

    storage.remove("worlds/Alpha/level.dat")
    assert not storage.exists("worlds/Alpha/level.dat")
    assert storage.exists("worlds/Alpha")

    storage.remove("worlds/Alpha")
    assert not storage.exists("worlds/Alpha")


def test_path_devuelve_la_raiz_resuelta(storage: LocalServerStorage, tmp_path: Path) -> None:
    assert storage.path() == str((tmp_path / "server-data").resolve())


# -- path traversal -----------------------------------------------------------


@pytest.mark.parametrize(
    "rel",
    [
        "..",
        "../escaped",
        "worlds/../../etc/passwd",
        "a/../../b",
        "..\\windows",
    ],
)
def test_rechaza_path_traversal(storage: LocalServerStorage, rel: str) -> None:
    with pytest.raises(StorageError):
        storage.write(rel, b"x")
    with pytest.raises(StorageError):
        storage.exists(rel)
    with pytest.raises(StorageError):
        storage.read(rel)


@pytest.mark.parametrize(
    "rel",
    [
        "/etc/passwd",
        "/worlds",
        "C:/windows",
        "//server/share",
    ],
)
def test_rechaza_rutas_absolutas(storage: LocalServerStorage, rel: str) -> None:
    with pytest.raises(StorageError):
        storage.exists(rel)
    with pytest.raises(StorageError):
        storage.write(rel, b"x")


def test_rechaza_rel_vacio(storage: LocalServerStorage) -> None:
    with pytest.raises(StorageError):
        storage.read("")
    with pytest.raises(StorageError):
        storage.write("", b"x")


def test_no_escribe_nada_fuera_de_la_raiz_al_rechazar(storage: LocalServerStorage) -> None:
    with pytest.raises(StorageError):
        storage.write("worlds/../../sneaky", b"boom")
    assert not Path(storage.path()).parent.joinpath("sneaky").exists()


# -- symlinks maliciosos -------------------------------------------------------


def test_symlink_que_escapa_de_la_raiz_se_rechaza(
    storage: LocalServerStorage, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    os.symlink(outside, storage.path() + "/link")

    with pytest.raises(StorageError):
        storage.read("link/secret.txt")
    with pytest.raises(StorageError):
        storage.exists("link/secret.txt")
    with pytest.raises(StorageError):
        storage.write("link/evil.txt", b"x")


def test_symlink_dentro_de_la_raiz_si_es_valido(
    storage: LocalServerStorage, tmp_path: Path
) -> None:
    storage.write("worlds/Alpha/level.dat", b"\x0a\x00\x00")
    os.symlink("worlds", storage.path() + "/alias")

    assert storage.exists("alias/Alpha/level.dat")
    assert storage.read("alias/Alpha/level.dat") == b"\x0a\x00\x00"


def test_no_se_puede_crear_symlink_fuera_desde_un_write_relativo(
    storage: LocalServerStorage, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    storage.write("worlds/Alpha/level.dat", b"\x0a\x00\x00")
    os.symlink(outside, storage.path() + "/worlds/Alpha/escape")

    with pytest.raises(StorageError):
        storage.read("worlds/Alpha/escape/pwned.txt")


# -- list_worlds / disk_stats ---------------------------------------------------


def test_list_worlds_enumera_mundos_con_level_dat(storage_with_world: LocalServerStorage) -> None:
    worlds = storage_with_world.list_worlds()
    assert len(worlds) == 1
    assert worlds[0]["name"] == "Alpha"
    assert worlds[0]["level_name"] == "Alpha"
    assert worlds[0]["size_bytes"] > 0


def test_list_worlds_ignora_dirs_sin_level_dat(storage: LocalServerStorage) -> None:
    storage.write("worlds/NoWorld/foo.txt", b"x")
    assert storage.list_worlds() == []


def test_disk_stats_devuelve_uso_de_espacio(storage: LocalServerStorage) -> None:
    stats = storage.disk_stats()
    assert stats["total"] > 0
    assert stats["free"] >= 0
    assert stats["root_bytes"] >= 0


# -- snapshots (streams) ---------------------------------------------------------


def test_world_snapshot_genera_zip_y_write_snapshot_lo_restaura(
    storage_with_world: LocalServerStorage, tmp_path: Path
) -> None:
    stream = storage_with_world.world_snapshot("Alpha")
    try:
        assert stream is not None
        head = stream.read(2)
        assert head == b"PK"
        stream.seek(0)
        storage_with_world.write_snapshot("worlds/AlphaCopy", stream)
    finally:
        stream.close()

    assert storage_with_world.exists("worlds/AlphaCopy/level.dat")
    assert storage_with_world.read("worlds/AlphaCopy/level.dat") == b"\x0a\x00\x00"
    assert storage_with_world.exists("worlds/AlphaCopy/db/1.lbd")


def test_write_snapshot_restaura_zip_con_directorio_envolvente(
    storage: LocalServerStorage,
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("MyWorld/level.dat", b"\x0a\x00\x00")
        zf.writestr("MyWorld/db/1.lbd", b"chunk")
    buffer.seek(0)

    storage.write_snapshot("worlds/Beta", buffer)

    assert storage.exists("worlds/Beta/level.dat")
    assert storage.exists("worlds/Beta/db/1.lbd")


def test_write_snapshot_restaura_tar_gz(
    storage: LocalServerStorage,
) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
        for name, payload in (
            ("Gamma/level.dat", b"\x0a\x00\x00"),
            ("Gamma/db/1.lbd", b"chunk"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    buffer.seek(0)

    storage.write_snapshot("worlds/Gamma", buffer)

    assert storage.exists("worlds/Gamma/level.dat")
    assert storage.exists("worlds/Gamma/db/1.lbd")


@pytest.mark.parametrize(
    "member_name",
    [
        "../evil.txt",
        "../../etc/passwd",
        "/absolute/evil.txt",
        "worlds/../../outside.txt",
    ],
)
def test_write_snapshot_rechaza_zip_slip(storage: LocalServerStorage, member_name: str) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(member_name, b"evil")
    buffer.seek(0)

    with pytest.raises(StorageError):
        storage.write_snapshot("worlds/Safe", buffer)

    assert not Path(storage.path()).parent.joinpath("evil.txt").exists()


def test_write_snapshot_rechaza_tar_symlink(
    storage: LocalServerStorage,
) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tf:
        info = tarfile.TarInfo("worlds/Safe/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc"
        tf.addfile(info)
    buffer.seek(0)

    with pytest.raises(StorageError):
        storage.write_snapshot("worlds/Safe", buffer)


def test_write_snapshot_rechaza_formato_desconocido(storage: LocalServerStorage) -> None:
    with pytest.raises(StorageError):
        storage.write_snapshot("worlds/Safe", io.BytesIO(b"not a snapshot"))


# -- locks ----------------------------------------------------------------------


async def test_lock_unlock_es_exclusivo_por_scope(storage: LocalServerStorage) -> None:
    await storage.lock("backup:worlds")
    assert storage._locks["backup:worlds"].locked()
    await storage.unlock("backup:worlds")
    assert not storage._locks["backup:worlds"].locked()


async def test_unlock_sin_lock_es_no_op(storage: LocalServerStorage) -> None:
    await storage.unlock("never-locked")
