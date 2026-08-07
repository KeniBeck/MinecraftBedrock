"""Tests del adaptador ``LocalBackupStore`` (Fase F paso 13, §8.5).

Cubre put/get/delete/exists/list/verify y la validación de referencias contra
path traversal (mismo criterio de defensa-in-depth que ``LocalServerStorage``,
§22).
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from app.infrastructure.backups.local import LocalBackupStore
from app.kernel.errors import BackupStoreError


def make_bytes(payload: bytes = b"artefacto") -> io.BytesIO:
    return io.BytesIO(payload)


def test_put_y_get_roundtrip(tmp_path: Path) -> None:
    store = LocalBackupStore(tmp_path)
    stream = make_bytes(b"contenido")

    store.put("srv-1/bk-1.tar.zst", stream)

    assert store.exists("srv-1/bk-1.tar.zst")
    with store.get("srv-1/bk-1.tar.zst") as handle:
        assert handle.read() == b"contenido"


def test_put_crea_directorios_intermedios(tmp_path: Path) -> None:
    store = LocalBackupStore(tmp_path)

    store.put("a/b/c/art.tar.zst", make_bytes())

    assert store.exists("a/b/c/art.tar.zst")


def test_put_sobrescribe_artefacto_existente(tmp_path: Path) -> None:
    store = LocalBackupStore(tmp_path)
    store.put("srv-1/bk.tar.zst", make_bytes(b"v1"))

    store.put("srv-1/bk.tar.zst", make_bytes(b"v2"))

    with store.get("srv-1/bk.tar.zst") as handle:
        assert handle.read() == b"v2"


def test_get_de_ref_inexistente_fracasa(tmp_path: Path) -> None:
    store = LocalBackupStore(tmp_path)

    with pytest.raises(BackupStoreError):
        store.get("srv-1/nope.tar.zst")


def test_delete_elimina_el_artefacto(tmp_path: Path) -> None:
    store = LocalBackupStore(tmp_path)
    store.put("srv-1/bk.tar.zst", make_bytes())

    store.delete("srv-1/bk.tar.zst")

    assert not store.exists("srv-1/bk.tar.zst")


def test_list_lista_artefactos_relativos(tmp_path: Path) -> None:
    store = LocalBackupStore(tmp_path)
    store.put("srv-1/bk-1.tar.zst", make_bytes())
    store.put("srv-2/bk-2.tar.zst", make_bytes())

    refs = store.list()

    assert sorted(refs) == ["srv-1/bk-1.tar.zst", "srv-2/bk-2.tar.zst"]


def test_list_por_prefijo(tmp_path: Path) -> None:
    store = LocalBackupStore(tmp_path)
    store.put("srv-1/bk-1.tar.zst", make_bytes())
    store.put("srv-2/bk-2.tar.zst", make_bytes())

    assert store.list("srv-1") == ["srv-1/bk-1.tar.zst"]


def test_verify_ok_y_ko(tmp_path: Path) -> None:
    store = LocalBackupStore(tmp_path)
    store.put("srv-1/bk.tar.zst", make_bytes(b"contenido"))
    good = hashlib.sha256(b"contenido").hexdigest()

    assert store.verify("srv-1/bk.tar.zst", good) is True
    assert store.verify("srv-1/bk.tar.zst", "x" * 64) is False
    assert store.verify("srv-1/nope.tar.zst", good) is False


@pytest.mark.parametrize(
    "ref",
    ["", "  ", "/abs/path", "a/../b", "..", "a/../../b", "a\\b", "a\\..\\b"],
)
def test_ref_invalida_fracasa(tmp_path: Path, ref: str) -> None:
    store = LocalBackupStore(tmp_path)

    with pytest.raises(BackupStoreError):
        store.get(ref)
