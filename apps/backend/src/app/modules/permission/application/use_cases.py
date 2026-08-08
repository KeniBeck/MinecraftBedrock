"""Use cases del módulo Permission (Blueprint §3.6).

Flujos: leer/escribir ``allowlist.json`` y ``permissions.json`` vía
``ServerStoragePort``; enviar comandos ``allowlist``/``op``/``deop`` vía la
facade Console cuando el servidor está corriendo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.kernel.events.bus import EventBusPort
from app.kernel.ports.runtime import ServerState
from app.kernel.ports.storage import ServerStoragePort
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.ports import ServerConsoleReader
from app.modules.permission.application.ports import PermissionStorageResolver
from app.modules.permission.domain.entities import (
    AllowlistEntry,
    PermissionEntry,
    PermissionLevel,
)
from app.modules.permission.domain.errors import (
    PermissionNotFoundError,
    PermissionValidationError,
)
from app.modules.permission.domain.events import allowlist_toggled, player_operator_changed

_ALLOWLIST_FILE = "allowlist.json"
_PERMISSIONS_FILE = "permissions.json"


@dataclass(slots=True)
class PermissionDeps:
    """Dependencias comunes de los use cases del módulo Permission."""

    storage: PermissionStorageResolver
    console: ConsoleFacade
    server: ServerConsoleReader
    bus: EventBusPort


async def _server_is_running(deps: PermissionDeps, server_id: str) -> bool:
    server = await deps.server.get_server(server_id)
    return server is not None and server.state is ServerState.RUNNING


def _read_json(storage: ServerStoragePort, rel: str) -> list[dict[str, Any]]:
    if not storage.exists(rel):
        return []
    raw = storage.read(rel)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PermissionValidationError(
            f"El archivo {rel} no es JSON válido",
            context={"rel": rel, "error": str(exc)},
        ) from exc
    if not isinstance(data, list):
        raise PermissionValidationError(
            f"El archivo {rel} no contiene un array JSON",
            context={"rel": rel},
        )
    return data


def _write_json(storage: ServerStoragePort, rel: str, data: list[dict[str, Any]]) -> None:
    storage.write(rel, json.dumps(data, indent=2).encode("utf-8") + b"\n")


# -- allowlist ----------------------------------------------------------------


async def add_to_allowlist(
    deps: PermissionDeps,
    server_id: str,
    name: str,
    xuid: str,
    ignores_player_limit: bool = False,
) -> AllowlistEntry:
    name = name.strip()
    xuid = xuid.strip()
    if not name:
        raise PermissionValidationError("name requerido", context={"name": name})
    if not xuid:
        raise PermissionValidationError("xuid requerido", context={"xuid": xuid})

    storage = deps.storage.for_server(server_id)
    entries = _read_json(storage, _ALLOWLIST_FILE)
    storage = deps.storage.for_server(server_id)
    entries = _read_json(storage, _ALLOWLIST_FILE)
    for entry in entries:
        if entry.get("xuid") == xuid or entry.get("name") == name:
            raise PermissionValidationError(
                "La entrada ya existe en la allowlist",
                context={"name": name, "xuid": xuid},
            )

    entries.append({"ignoresPlayerLimit": ignores_player_limit, "name": name, "xuid": xuid})
    _write_json(storage, _ALLOWLIST_FILE, entries)

    if await _server_is_running(deps, server_id):
        await deps.console.send_command(
            SendCommand(server_id=server_id, command=f"allowlist add {name}")
        )

    return AllowlistEntry(name=name, xuid=xuid, ignores_player_limit=ignores_player_limit)


async def remove_from_allowlist(deps: PermissionDeps, server_id: str, xuid: str) -> None:
    xuid = xuid.strip()
    if not xuid:
        raise PermissionValidationError("xuid requerido", context={"xuid": xuid})

    storage = deps.storage.for_server(server_id)
    entries = _read_json(storage, _ALLOWLIST_FILE)
    removed_name: str | None = None
    new_entries: list[dict[str, Any]] = []
    for entry in entries:
        if entry.get("xuid") == xuid:
            removed_name = entry.get("name", "")
            continue
        new_entries.append(entry)

    if removed_name is None:
        raise PermissionNotFoundError(
            "Entrada no encontrada en la allowlist",
            context={"xuid": xuid},
        )

    _write_json(storage, _ALLOWLIST_FILE, new_entries)

    if removed_name and await _server_is_running(deps, server_id):
        await deps.console.send_command(
            SendCommand(server_id=server_id, command=f"allowlist remove {removed_name}")
        )


async def list_allowlist(deps: PermissionDeps, server_id: str) -> list[AllowlistEntry]:
    storage = deps.storage.for_server(server_id)
    entries = _read_json(storage, _ALLOWLIST_FILE)
    return [
        AllowlistEntry(
            name=e.get("name", ""),
            xuid=e.get("xuid", ""),
            ignores_player_limit=e.get("ignoresPlayerLimit", False),
        )
        for e in entries
    ]


async def set_allowlist_enabled(
    deps: PermissionDeps,
    server_id: str,
    enabled: bool,
    *,
    actor_id: str | None = None,
) -> None:
    """Activa/desactiva ``ALLOW_LIST`` (env) publicando ``ALLOWLIST_TOGGLED``.

    Server consume el evento y inyecta ``ALLOW_LIST=<true/false>`` en el spec
    antes de renderizar, recreando el contenedor (mismo mecanismo que
    ``WORLD.ACTIVATED``/``LEVEL_NAME``).
    """
    await deps.bus.publish(allowlist_toggled(server_id, enabled=enabled, actor_id=actor_id))


# -- permissions --------------------------------------------------------------


async def set_permission_level(
    deps: PermissionDeps,
    server_id: str,
    xuid: str,
    level: PermissionLevel,
    *,
    actor_id: str | None = None,
) -> PermissionEntry:
    xuid = xuid.strip()
    if not xuid:
        raise PermissionValidationError("xuid requerido", context={"xuid": xuid})

    storage = deps.storage.for_server(server_id)
    entries = _read_json(storage, _PERMISSIONS_FILE)
    found = False
    for entry in entries:
        if entry.get("xuid") == xuid:
            entry["permission"] = level.value
            found = True
            break
    if not found:
        entries.append({"permission": level.value, "xuid": xuid})

    _write_json(storage, _PERMISSIONS_FILE, entries)

    if await _server_is_running(deps, server_id):
        if level is PermissionLevel.OPERATOR:
            await deps.console.send_command(SendCommand(server_id=server_id, command=f"op {xuid}"))
        else:
            await deps.console.send_command(
                SendCommand(server_id=server_id, command=f"deop {xuid}")
            )

    await deps.bus.publish(
        player_operator_changed(
            server_id,
            xuid,
            operator=(level is PermissionLevel.OPERATOR),
            actor_id=actor_id,
        )
    )

    return PermissionEntry(xuid=xuid, level=level)


async def remove_permission(
    deps: PermissionDeps,
    server_id: str,
    xuid: str,
    *,
    actor_id: str | None = None,
) -> None:
    xuid = xuid.strip()
    if not xuid:
        raise PermissionValidationError("xuid requerido", context={"xuid": xuid})

    storage = deps.storage.for_server(server_id)
    entries = _read_json(storage, _PERMISSIONS_FILE)
    new_entries: list[dict[str, Any]] = []
    removed = False
    for entry in entries:
        if entry.get("xuid") == xuid:
            removed = True
            continue
        new_entries.append(entry)

    if not removed:
        raise PermissionNotFoundError(
            "Entrada de permiso no encontrada",
            context={"xuid": xuid},
        )

    _write_json(storage, _PERMISSIONS_FILE, new_entries)

    if await _server_is_running(deps, server_id):
        await deps.console.send_command(SendCommand(server_id=server_id, command=f"deop {xuid}"))

    await deps.bus.publish(
        player_operator_changed(server_id, xuid, operator=False, actor_id=actor_id)
    )


async def list_permissions(deps: PermissionDeps, server_id: str) -> list[PermissionEntry]:
    storage = deps.storage.for_server(server_id)
    entries = _read_json(storage, _PERMISSIONS_FILE)
    result: list[PermissionEntry] = []
    for e in entries:
        raw = e.get("permission", "")
        try:
            level = PermissionLevel(raw)
        except ValueError:
            continue
        result.append(PermissionEntry(xuid=e.get("xuid", ""), level=level))
    return result
