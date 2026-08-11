"""Lector best-effort de ``level.dat`` de Bedrock (NBT little-endian + gzip).

El MVP solo exigía la presencia de ``level.dat`` (validación NBT fuera de
alcance, §22); este módulo añade una lectura **best effort** de los ajustes del
mundo que se guardan en él (``seed``, ``gamemode``, ``difficulty``) para que
``ScanWorldsUseCase`` pueda rellenar la metadata al sincronizar. Nunca lanza:
si el archivo está corrupto, bloqueado o en un formato inesperado devuelve un
dict vacío y el sync sigue con lo que ya había en metadata.
"""

from __future__ import annotations

import gzip
import struct
from pathlib import Path
from typing import Any

# Tag types NBT (Bedrock = little endian).
_TAG_END = 0
_TAG_BYTE = 1
_TAG_SHORT = 2
_TAG_INT = 3
_TAG_LONG = 4
_TAG_FLOAT = 5
_TAG_DOUBLE = 6
_TAG_BYTE_ARRAY = 7
_TAG_STRING = 8
_TAG_LIST = 9
_TAG_COMPOUND = 10
_TAG_INT_ARRAY = 11
_TAG_LONG_ARRAY = 12

_GAMEMODE: dict[int, str] = {0: "survival", 1: "creative", 2: "adventure"}
_DIFFICULTY: dict[int, str] = {0: "peaceful", 1: "easy", 2: "normal", 3: "hard"}

_VIEW_DISTANCE_KEY = "view-distance"


class _Reader:
    """Cursor de lectura sobre el payload NBT (todos los ints little-endian)."""

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def u8(self) -> int:
        value = self.data[self.pos]
        self.pos += 1
        return value

    def u16(self) -> int:
        value = int.from_bytes(self.data[self.pos : self.pos + 2], "little")
        self.pos += 2
        return value

    def i32(self) -> int:
        value = int.from_bytes(self.data[self.pos : self.pos + 4], "little", signed=True)
        self.pos += 4
        return value

    def i64(self) -> int:
        value = int.from_bytes(self.data[self.pos : self.pos + 8], "little", signed=True)
        self.pos += 8
        return value

    def utf8(self) -> str:
        length = self.u16()
        value = self.data[self.pos : self.pos + length].decode("utf-8", errors="replace")
        self.pos += length
        return value


def decode_level_dat(data: bytes) -> dict[str, Any] | None:
    """Decodifica un ``level.dat`` a su compound raíz, o ``None``.

    BDS moderno (1.26.x) escribe ``level.dat`` **sin gzip** y con cabecera de
    8 bytes (``0a 00 00 00`` + longitud LE del payload); versiones antiguas lo
    escriben gzip directamente. Acepta ambos y además el formato crudo sin
    cabecera. Es un parser genérico de NBT little-endian que tolera cualquier
    tag; nunca lanza sobre datos inválidos (devuelve ``None``).
    """
    try:
        if data[:2] == b"\x1f\x8b":
            raw = _strip_level_header(gzip.decompress(data))
        else:
            raw = _strip_level_header(data)
        reader = _Reader(raw)
        tag = reader.u8()
        if tag != _TAG_COMPOUND:
            return None
        reader.utf8()  # nombre de la raíz
        value = _decode(reader, _TAG_COMPOUND)
        if not isinstance(value, dict):
            return None
        return value
    except (OSError, IndexError, ValueError, gzip.BadGzipFile):
        return None


def _strip_level_header(data: bytes) -> bytes:
    """Quita la cabecera de 8 bytes del ``level.dat`` moderno, si la tiene.

    Formato observado en BDS 1.26.x: ``0a 00 00 00`` (marcador) seguido de la
    longitud LE del payload NBT. Solo se descarta cuando el marcador y la
    longitud declarada son coherentes; si no, se devuelve el payload tal cual
    (evita romper NBT crudo normal o archivos corruptos).
    """
    if data[:4] == b"\x0a\x00\x00\x00" and len(data) >= 8:
        declared = int.from_bytes(data[4:8], "little")
        if declared >= 0 and 4 + declared <= len(data):
            return data[8 : 8 + declared]
    return data


def _decode(reader: _Reader, tag: int) -> Any:
    if tag == _TAG_BYTE:
        value = int.from_bytes(reader.data[reader.pos : reader.pos + 1], "little", signed=True)
        reader.pos += 1
        return value
    if tag == _TAG_SHORT:
        value = int.from_bytes(reader.data[reader.pos : reader.pos + 2], "little", signed=True)
        reader.pos += 2
        return value
    if tag == _TAG_INT:
        return reader.i32()
    if tag == _TAG_LONG:
        return reader.i64()
    if tag == _TAG_FLOAT:
        return _read_float(reader)
    if tag == _TAG_DOUBLE:
        return _read_double(reader)
    if tag == _TAG_BYTE_ARRAY:
        length = reader.i32()
        chunk = reader.data[reader.pos : reader.pos + length]
        reader.pos += length
        return chunk
    if tag == _TAG_STRING:
        return reader.utf8()
    if tag == _TAG_LIST:
        element_type = reader.u8()
        count = reader.i32()
        return [_decode(reader, element_type) for _ in range(count)]
    if tag == _TAG_COMPOUND:
        obj: dict[str, Any] = {}
        while True:
            element_tag = reader.u8()
            if element_tag == _TAG_END:
                return obj
            name = reader.utf8()
            obj[name] = _decode(reader, element_tag)
        return obj
    if tag == _TAG_INT_ARRAY:
        length = reader.i32()
        return [reader.i32() for _ in range(length)]
    if tag == _TAG_LONG_ARRAY:
        length = reader.i32()
        return [reader.i64() for _ in range(length)]
    return None


def _skip(reader: _Reader, tag: int) -> None:
    """Avanza el cursor pasando un valor del tag dado (sin construir estructuras)."""
    if tag == _TAG_BYTE:
        reader.pos += 1
    elif tag == _TAG_SHORT:
        reader.pos += 2
    elif tag == _TAG_INT:
        reader.pos += 4
    elif tag == _TAG_LONG:
        reader.pos += 8
    elif tag == _TAG_FLOAT:
        reader.pos += 4
    elif tag == _TAG_DOUBLE:
        reader.pos += 8
    elif tag == _TAG_BYTE_ARRAY:
        reader.pos += 4 + reader.i32()
    elif tag == _TAG_STRING:
        reader.utf8()
    elif tag == _TAG_LIST:
        element_type = reader.u8()
        count = reader.i32()
        for _ in range(count):
            _skip(reader, element_type)
    elif tag == _TAG_COMPOUND:
        while True:
            element_tag = reader.u8()
            if element_tag == _TAG_END:
                return
            reader.utf8()
            _skip(reader, element_tag)
    elif tag == _TAG_INT_ARRAY:
        reader.pos += 4 + 4 * reader.i32()
    elif tag == _TAG_LONG_ARRAY:
        reader.pos += 4 + 8 * reader.i32()


def _find_level_name(payload: bytes) -> int | None:
    """Posición del prefix de longitud del string ``LevelName``, o ``None``.

    NBT es secuencial (todo va prefixado por longitud, sin tablas de offset):
    localizar el string basta para reescribirlo rehaciendo solo ese tramo.
    """
    reader = _Reader(payload)
    tag = reader.u8()
    if tag != _TAG_COMPOUND:
        return None
    reader.utf8()  # nombre de la raíz
    while True:
        element_tag = reader.u8()
        if element_tag == _TAG_END:
            return None
        name = reader.utf8()
        if name == "LevelName" and element_tag == _TAG_STRING:
            return reader.pos
        _skip(reader, element_tag)


def patch_level_name(data: bytes, new_name: str) -> bytes | None:
    """Reemplaza el tag ``LevelName`` de un ``level.dat`` preservando el resto.

    Mantiene el formato de entrada (gzip o crudo y, si venía, la cabecera de
    8 bytes con la longitud actualizada). Devuelve los bytes reescritos o
    ``None`` si el nivel no se pudo parsear / no tiene ``LevelName``. Nunca
    lanza sobre datos inválidos.
    """
    try:
        gzipped = data[:2] == b"\x1f\x8b"
        raw = gzip.decompress(data) if gzipped else data
        payload = _strip_level_header(raw)
        pos = _find_level_name(payload)
        if pos is None:
            return None
        old_len = int.from_bytes(payload[pos : pos + 2], "little")
        if pos + 2 + old_len > len(payload):
            return None
        encoded = new_name.encode("utf-8")
        patched = (
            payload[:pos]
            + len(encoded).to_bytes(2, "little")
            + encoded
            + payload[pos + 2 + old_len :]
        )
        had_header = len(raw) - len(payload) == 8
        if had_header:
            patched = b"\x0a\x00\x00\x00" + len(patched).to_bytes(4, "little") + patched
        return gzip.compress(patched) if gzipped else patched
    except (IndexError, OSError, ValueError, gzip.BadGzipFile):
        return None


def read_world_settings(world_dir: Path) -> dict[str, Any]:
    """Ajustes del mundo desde su ``level.dat`` (best effort, dict parcial).

    Devuelve solo las claves que se pudieron leer: ``seed`` (str),
    ``gamemode`` (str), ``difficulty`` (str). Vacío si el nivel no se pudo
    parsear o las claves no existen.
    """
    level_dat = world_dir / "level.dat"
    try:
        data = level_dat.read_bytes()
    except OSError:
        return {}
    root = decode_level_dat(data)
    if root is None:
        return {}

    settings: dict[str, Any] = {}
    world_gen = root.get("WorldGenSettings")
    seed = world_gen.get("seed") if isinstance(world_gen, dict) else None
    if seed is None:
        seed = root.get("RandomSeed")
    if isinstance(seed, int):
        settings["seed"] = str(seed)

    gamemode = root.get("GameType")
    if isinstance(gamemode, int) and gamemode in _GAMEMODE:
        settings["gamemode"] = _GAMEMODE[gamemode]

    difficulty = root.get("Difficulty")
    if isinstance(difficulty, int) and difficulty in _DIFFICULTY:
        settings["difficulty"] = _DIFFICULTY[difficulty]

    return settings


def read_server_properties_view_distance(root: Path) -> int | None:
    """``view-distance`` de ``server.properties`` de la raíz, o ``None``.

    La distancia de chunks es un ajuste de servidor (no vive en ``level.dat``);
    se usa como fuente de respaldo para rellenar la metadata al sincronizar.
    """
    try:
        text = (root / "server.properties").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip() == _VIEW_DISTANCE_KEY:
            try:
                parsed = int(value.strip())
            except ValueError:
                return None
            return parsed if parsed >= 1 else None
    return None


def _read_float(reader: _Reader) -> float:
    value: float = struct.unpack("<f", reader.data[reader.pos : reader.pos + 4])[0]
    reader.pos += 4
    return value


def _read_double(reader: _Reader) -> float:
    value: float = struct.unpack("<d", reader.data[reader.pos : reader.pos + 8])[0]
    reader.pos += 8
    return value
