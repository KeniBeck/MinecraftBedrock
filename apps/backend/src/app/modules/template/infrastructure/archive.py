"""Artefacto ``.mctemplate`` (Blueprint §3.11): build/parse del zip.

Formato fijo por ser un archivo de plantilla que controlamos nosotros (mismo
enfoque zip que ``.mcworld`` de World, §22). Cada miembro se valida por nombre
exacto contra el conjunto esperado: un artefacto malformado o con path
traversal en sus miembros se rechaza al abrirse (``TEMPLATE.CORRUPT``).
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from typing import Any

from app.modules.template.domain.errors import TemplateCorruptError

# Versión de formato del artefacto (bump en rupturas de esquema del zip).
FORMAT_VERSION = 1

_MANIFEST = "manifest.json"
_WORLD_NAME = "world_name.txt"
_CONFIG = "config.json"
_WORLD = "world.mcworld"
_EXPECTED_MEMBERS = frozenset({_MANIFEST, _WORLD_NAME, _CONFIG, _WORLD})


@dataclass(frozen=True, slots=True)
class ParsedTemplate:
    """Descomposición de un artefacto ``.mctemplate`` para su reproducción."""

    name: str
    version: str
    origin_world: str
    properties: dict[str, str]
    world_name: str
    world_bytes: bytes


def build_template_archive(
    *,
    name: str,
    version: str,
    origin_world: str,
    properties: dict[str, str],
    world_bytes: bytes,
) -> bytes:
    """Empaqueta el estado capturado en un artefacto ``.mctemplate``."""
    buf = io.BytesIO()
    manifest = {
        "format_version": FORMAT_VERSION,
        "name": name,
        "version": version,
        "origin_world": origin_world,
    }
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        zf.writestr(_MANIFEST, json.dumps(manifest).encode("utf-8"))
        zf.writestr(_WORLD_NAME, origin_world.encode("utf-8"))
        zf.writestr(
            _CONFIG,
            json.dumps({"version": version, "properties": properties}).encode("utf-8"),
        )
        zf.writestr(_WORLD, world_bytes)
    return buf.getvalue()


def open_template_archive(data: bytes) -> ParsedTemplate:
    """Valida y descompone un artefacto; rechaza miembros inesperados/traversal."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        if set(zf.namelist()) != _EXPECTED_MEMBERS:
            raise TemplateCorruptError(
                "El artefacto no tiene la estructura esperada (.mctemplate)",
                context={"members": sorted(zf.namelist())},
            )
        manifest = _read_json(zf, _MANIFEST)
        world_name = _read_text(zf, _WORLD_NAME)
        config = _read_json(zf, _CONFIG)
        world_bytes = _read_bytes(zf, _WORLD)

    properties = config.get("properties")
    if not isinstance(properties, dict):
        raise TemplateCorruptError(
            "El artefacto no lleva config (properties)",
            context={"config": config},
        )
    return ParsedTemplate(
        name=str(manifest.get("name", "")),
        version=str(config.get("version") or ""),
        origin_world=world_name,
        properties={str(k): str(v) for k, v in properties.items()},
        world_name=world_name,
        world_bytes=world_bytes,
    )


def _read_bytes(zf: zipfile.ZipFile, member: str) -> bytes:
    try:
        raw = zf.read(member)
    except KeyError as exc:
        raise TemplateCorruptError(
            "El artefacto no contiene un miembro requerido",
            context={"member": member},
        ) from exc
    return raw if isinstance(raw, bytes) else bytes(raw)


def _read_json(zf: zipfile.ZipFile, member: str) -> dict[str, Any]:
    raw = _read_bytes(zf, member)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise TemplateCorruptError(
            "El artefacto tiene un miembro JSON inválido",
            context={"member": member},
        ) from exc
    if not isinstance(value, dict):
        raise TemplateCorruptError(
            "El artefacto tiene un miembro JSON no objeto",
            context={"member": member},
        )
    return value


def _read_text(zf: zipfile.ZipFile, member: str) -> str:
    return _read_bytes(zf, member).decode("utf-8", errors="replace").strip()
