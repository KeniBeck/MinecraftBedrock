"""Tests del lector best-effort de ``level.dat`` (NBT little-endian + gzip).

Cubre la extracción de ``seed``/``gamemode``/``difficulty`` del nivel, el
respaldo de ``view_distance`` desde ``server.properties`` y la tolerancia a
niveles corruptos (nunca lanza; dict vacío).
"""

from __future__ import annotations

import gzip
from pathlib import Path

from app.infrastructure.storage.level_reader import (
    decode_level_dat,
    patch_level_name,
    read_server_properties_view_distance,
    read_world_settings,
)


def _named(tag_type: int, name: str, payload: bytes) -> bytes:
    raw = name.encode("utf-8")
    return bytes([tag_type]) + len(raw).to_bytes(2, "little") + raw + payload


def _compound(pairs: list[tuple[str, int, bytes]]) -> bytes:
    out = b""
    for name, tag_type, payload in pairs:
        out += _named(tag_type, name, payload)
    return out + b"\x00"


def _string(value: str) -> bytes:
    raw = value.encode("utf-8")
    return len(raw).to_bytes(2, "little") + raw


def _byte(value: int) -> bytes:
    return value.to_bytes(1, "little", signed=True)


def _int(value: int) -> bytes:
    return value.to_bytes(4, "little", signed=True)


def _long(value: int) -> bytes:
    return value.to_bytes(8, "little", signed=True)


def _level_dat(pairs: list[tuple[str, int, bytes]]) -> bytes:
    root_name = _string("level")
    root = bytes([0x0A]) + root_name + _compound(pairs)
    return gzip.compress(root)


def _level_dat_modern(pairs: list[tuple[str, int, bytes]]) -> bytes:
    """Formato BDS 1.26.x: sin gzip, cabecera de 8 bytes + longitud LE."""
    root_name = _string("")
    payload = bytes([0x0A]) + root_name + _compound(pairs)
    return b"\x0a\x00\x00\x00" + len(payload).to_bytes(4, "little") + payload


def test_read_world_settings_formato_moderno_con_cabecera(tmp_path: Path) -> None:
    data = _level_dat_modern(
        [
            ("LevelName", 8, _string("Bedrock level")),
            ("GameType", 3, _int(0)),
            ("Difficulty", 3, _int(1)),
            ("RandomSeed", 4, _long(-299205636354301287)),
        ]
    )
    (tmp_path / "level.dat").write_bytes(data)

    settings = read_world_settings(tmp_path)

    assert settings == {
        "seed": "-299205636354301287",
        "gamemode": "survival",
        "difficulty": "easy",
    }


def test_read_world_settings_cabecera_con_longitud_incoherente_no_recorta(
    tmp_path: Path,
) -> None:
    """Si la longitud declarada no cuadra, no se recorta (best effort → vacío)."""
    data = _level_dat_modern([("GameType", 3, _int(1))])
    bogus = data[:4] + len(data).to_bytes(4, "little") + data[8:]
    (tmp_path / "level.dat").write_bytes(bogus)

    settings = read_world_settings(tmp_path)

    assert settings == {}


def test_read_world_settings_extrae_seed_gamemode_dificultad(tmp_path: Path) -> None:
    data = _level_dat(
        [
            ("LevelName", 8, _string("Mi Mundo 1")),
            ("GameType", 3, _int(1)),
            ("Difficulty", 3, _int(3)),
            ("RandomSeed", 3, _int(111)),
            (
                "WorldGenSettings",
                10,
                _compound([("seed", 4, _long(12345))]),
            ),
        ]
    )
    (tmp_path / "level.dat").write_bytes(data)

    settings = read_world_settings(tmp_path)

    assert settings == {"seed": "12345", "gamemode": "creative", "difficulty": "hard"}


def test_read_world_settings_usa_random_seed_sin_world_gen(tmp_path: Path) -> None:
    data = _level_dat(
        [
            ("GameType", 3, _int(2)),
            ("Difficulty", 3, _int(0)),
            ("RandomSeed", 3, _int(99)),
        ]
    )
    (tmp_path / "level.dat").write_bytes(data)

    settings = read_world_settings(tmp_path)

    assert settings == {"seed": "99", "gamemode": "adventure", "difficulty": "peaceful"}


def test_read_world_settings_ignora_valores_fuera_de_rango(tmp_path: Path) -> None:
    data = _level_dat(
        [
            ("GameType", 3, _int(7)),
            ("Difficulty", 3, _int(9)),
        ]
    )
    (tmp_path / "level.dat").write_bytes(data)

    settings = read_world_settings(tmp_path)

    assert settings == {}


def test_read_world_settings_nivel_corrupto_devuelve_vacio(tmp_path: Path) -> None:
    (tmp_path / "level.dat").write_bytes(b"\x0a\x00\x00")
    (tmp_path / "level.dat.bak").write_bytes(b"no-sirve")

    assert read_world_settings(tmp_path) == {}
    assert read_world_settings(tmp_path / "level.dat.bak") == {}


def test_read_world_settings_sin_archivo_devuelve_vacio(tmp_path: Path) -> None:
    assert read_world_settings(tmp_path) == {}


def test_read_world_settings_lee_nivel_crudo_sin_gzip(tmp_path: Path) -> None:
    root_name = _string("level")
    root = bytes([0x0A]) + root_name + _compound([("GameType", 3, _int(1))])
    (tmp_path / "level.dat").write_bytes(root)

    settings = read_world_settings(tmp_path)

    assert settings == {"gamemode": "creative"}


def test_read_server_properties_view_distance(tmp_path: Path) -> None:
    (tmp_path / "server.properties").write_text(
        "server-name=Survival\nview-distance=12\n# comentario\n",
        encoding="utf-8",
    )

    assert read_server_properties_view_distance(tmp_path) == 12


def test_read_server_properties_view_distance_ausente_o_invalido(tmp_path: Path) -> None:
    (tmp_path / "server.properties").write_text("server-name=Survival\n", encoding="utf-8")

    assert read_server_properties_view_distance(tmp_path) is None

    (tmp_path / "server.properties").write_text(
        "view-distance=abc\n",
        encoding="utf-8",
    )

    assert read_server_properties_view_distance(tmp_path) is None

    assert read_server_properties_view_distance(tmp_path / "nope") is None


# -- patch_level_name ----------------------------------------------------------


def test_patch_level_name_formato_moderno_actualiza_cabecera() -> None:
    data = _level_dat_modern(
        [
            ("LevelName", 8, _string("Bedrock level")),
            ("GameType", 3, _int(0)),
            ("Difficulty", 3, _int(1)),
        ]
    )

    patched = patch_level_name(data, "village")

    assert patched is not None
    # Cabecera con longitud coherente y decodificable.
    assert patched[:4] == b"\x0a\x00\x00\x00"
    declared = int.from_bytes(patched[4:8], "little")
    assert 4 + declared <= len(patched)
    root = decode_level_dat(patched)
    assert root is not None
    assert root["LevelName"] == "village"
    assert root["GameType"] == 0
    assert root["Difficulty"] == 1


def test_patch_level_name_gzip_mantiene_formato() -> None:
    data = _level_dat([("LevelName", 8, _string("Bedrock level"))])

    patched = patch_level_name(data, "Mi Mundo 1")

    assert patched is not None
    assert patched[:2] == b"\x1f\x8b"
    root = decode_level_dat(patched)
    assert root is not None
    assert root["LevelName"] == "Mi Mundo 1"


def test_patch_level_name_preserva_el_resto_de_tags() -> None:
    data = _level_dat(
        [
            ("LevelName", 8, _string("Bedrock level")),
            ("GameType", 3, _int(2)),
            ("Difficulty", 3, _int(3)),
            ("RandomSeed", 4, _long(-299205636354301287)),
            ("byte", 1, _byte(1)),
            ("flags", 11, (1).to_bytes(4, "little") + _int(42)),
            ("lista", 9, bytes([3]) + (1).to_bytes(4, "little") + _int(7)),
        ]
    )

    patched = patch_level_name(data, "Nuevo")
    before = decode_level_dat(data)
    after = decode_level_dat(patched)

    assert after is not None
    assert after["LevelName"] == "Nuevo"
    for key, value in after.items():
        if key != "LevelName":
            assert value == before[key], f"{key} cambió: {value!r} != {before[key]!r}"


def test_patch_level_name_crudo_sin_cabecera_no_anade_cabecera() -> None:
    root_name = _string("level")
    root = bytes([0x0A]) + root_name + _compound([("LevelName", 8, _string("a"))])

    patched = patch_level_name(root, "b")

    assert patched is not None
    assert patched[:4] != b"\x0a\x00\x00\x00"
    assert decode_level_dat(patched) == {"LevelName": "b"}


def test_patch_level_name_sin_level_name_o_corrupto_devuelve_none() -> None:
    assert patch_level_name(_level_dat([("GameType", 3, _int(0))]), "x") is None
    assert patch_level_name(b"\x0a\x00\x00", "x") is None
    assert patch_level_name(b"no-sirve", "x") is None
