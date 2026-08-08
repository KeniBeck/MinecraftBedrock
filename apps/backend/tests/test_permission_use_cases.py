"""Tests de los use cases del módulo Permission (Blueprint §3.6)."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.infrastructure.storage.local import LocalServerStorage
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerState
from app.modules.console.application.commands import SendCommand
from app.modules.permission.application import use_cases
from app.modules.permission.application.use_cases import PermissionDeps
from app.modules.permission.domain.entities import PermissionLevel
from app.modules.permission.domain.errors import (
    PermissionNotFoundError,
    PermissionValidationError,
)
from app.modules.permission.domain.events import (
    ALLOWLIST_TOGGLED,
    PLAYER_OPERATOR_CHANGED,
)
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeServerReader

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_view(
    server_id: str = "srv-1",
    state: ServerState = ServerState.RUNNING,
    runtime_id: str = "r1",
) -> ServerView:
    return ServerView(
        id=server_id,
        name="Survival",
        state=state,
        version="1.20.0",
        image_ref="img:latest",
        runtime_id=runtime_id,
        created_at=NOW,
        updated_at=NOW,
        connection=stub_connection(),
    )


class FakeStorageResolver:
    def __init__(self, storage: LocalServerStorage) -> None:
        self._storage = storage

    def for_server(self, server_id: str) -> LocalServerStorage:
        del server_id
        return self._storage


class RecordingConsoleFacade:
    def __init__(self) -> None:
        self.commands: list[SendCommand] = []

    async def send_command(self, cmd: SendCommand) -> None:
        self.commands.append(cmd)


def make_deps(
    server_state: ServerState = ServerState.RUNNING,
) -> tuple[
    PermissionDeps,
    LocalServerStorage,
    RecordingConsoleFacade,
    InProcessEventBus,
    FakeServerReader,
]:
    storage = LocalServerStorage(Path(tempfile.mkdtemp(prefix="perm-test-")))
    console = RecordingConsoleFacade()
    bus = InProcessEventBus()
    server_reader = FakeServerReader(views={"srv-1": make_view(state=server_state)})
    deps = PermissionDeps(
        storage=FakeStorageResolver(storage),
        console=console,  # type: ignore[arg-type]
        server=server_reader,
        bus=bus,
    )
    return deps, storage, console, bus, server_reader


# -- allowlist ----------------------------------------------------------------


async def test_add_to_allowlist_escribe_archivo() -> None:
    deps, storage, console, _, _ = make_deps()
    entry = await use_cases.add_to_allowlist(deps, "srv-1", "TestPlayer", "12345")
    assert entry.name == "TestPlayer"
    assert entry.xuid == "12345"
    assert not entry.ignores_player_limit
    raw = storage.read("allowlist.json")
    data = json.loads(raw)
    assert len(data) == 1
    assert data[0]["name"] == "TestPlayer"
    assert data[0]["xuid"] == "12345"


async def test_add_to_allowlist_duplicado_rechazado() -> None:
    deps, storage, _, _, _ = make_deps()
    storage.write(
        "allowlist.json",
        b'[{"ignoresPlayerLimit":false,"name":"TestPlayer","xuid":"12345"}]\n',
    )
    with pytest.raises(PermissionValidationError, match="ya existe"):
        await use_cases.add_to_allowlist(deps, "srv-1", "TestPlayer", "12345")


async def test_add_to_allowlist_envia_comando_si_corre() -> None:
    deps, _, console, _, _ = make_deps(ServerState.RUNNING)
    await use_cases.add_to_allowlist(deps, "srv-1", "TestPlayer", "12345")
    assert len(console.commands) == 1
    assert console.commands[0].command == "allowlist add TestPlayer"


async def test_add_to_allowlist_no_envia_si_detenido() -> None:
    deps, _, console, _, _ = make_deps(ServerState.STOPPED)
    await use_cases.add_to_allowlist(deps, "srv-1", "TestPlayer", "12345")
    assert len(console.commands) == 0


async def test_remove_from_allowlist_quita_y_envia() -> None:
    deps, storage, console, _, _ = make_deps(ServerState.RUNNING)
    storage.write(
        "allowlist.json",
        b'[{"ignoresPlayerLimit":false,"name":"TestPlayer","xuid":"12345"}]\n',
    )
    await use_cases.remove_from_allowlist(deps, "srv-1", "12345")
    data = json.loads(storage.read("allowlist.json"))
    assert len(data) == 0
    assert console.commands[0].command == "allowlist remove TestPlayer"


async def test_remove_from_allowlist_no_encontrado() -> None:
    deps, _, _, _, _ = make_deps()
    with pytest.raises(PermissionNotFoundError):
        await use_cases.remove_from_allowlist(deps, "srv-1", "00000")


async def test_list_allowlist() -> None:
    deps, storage, _, _, _ = make_deps()
    storage.write(
        "allowlist.json",
        b'[{"ignoresPlayerLimit":true,"name":"A","xuid":"1"},'
        b'{"ignoresPlayerLimit":false,"name":"B","xuid":"2"}]\n',
    )
    entries = await use_cases.list_allowlist(deps, "srv-1")
    assert len(entries) == 2
    assert entries[0].name == "A"
    assert entries[1].ignores_player_limit is False


async def test_list_allowlist_vacio() -> None:
    deps, _, _, _, _ = make_deps()
    entries = await use_cases.list_allowlist(deps, "srv-1")
    assert entries == []


async def test_set_allowlist_enabled_publica_evento() -> None:
    deps, _, _, bus, _ = make_deps()
    events: list[DomainEvent] = []
    bus.subscribe("permission.allowlist_toggled", events.append)
    await use_cases.set_allowlist_enabled(deps, "srv-1", True, actor_id="user-1")
    assert len(events) == 1
    assert events[0].type == ALLOWLIST_TOGGLED
    assert events[0].server_id == "srv-1"
    assert events[0].payload == {"server_id": "srv-1", "enabled": True}
    assert events[0].actor_id == "user-1"


async def test_set_allowlist_enabled_false_publica_evento() -> None:
    deps, _, _, bus, _ = make_deps()
    events: list[DomainEvent] = []
    bus.subscribe("permission.allowlist_toggled", events.append)
    await use_cases.set_allowlist_enabled(deps, "srv-1", False)
    assert events[0].payload["enabled"] is False


# -- permissions --------------------------------------------------------------


async def test_set_permission_escribe_y_publica() -> None:
    deps, storage, console, bus, _ = make_deps(ServerState.RUNNING)
    events: list[DomainEvent] = []
    bus.subscribe("player.operator_changed", events.append)
    entry = await use_cases.set_permission_level(deps, "srv-1", "12345", PermissionLevel.OPERATOR)
    assert entry.xuid == "12345"
    assert entry.level is PermissionLevel.OPERATOR
    raw = storage.read("permissions.json")
    data = json.loads(raw)
    assert len(data) == 1
    assert data[0]["permission"] == "operator"
    assert console.commands[0].command == "op 12345"
    assert len(events) == 1
    assert events[0].type == PLAYER_OPERATOR_CHANGED


async def test_set_permission_member_envia_deop() -> None:
    deps, _, console, _, _ = make_deps(ServerState.RUNNING)
    await use_cases.set_permission_level(deps, "srv-1", "12345", PermissionLevel.MEMBER)
    assert console.commands[0].command == "deop 12345"


async def test_set_permission_actualiza_existente() -> None:
    deps, storage, _, _, _ = make_deps()
    storage.write("permissions.json", b'[{"permission":"visitor","xuid":"12345"}]\n')
    entry = await use_cases.set_permission_level(deps, "srv-1", "12345", PermissionLevel.OPERATOR)
    assert entry.level is PermissionLevel.OPERATOR
    data = json.loads(storage.read("permissions.json"))
    assert len(data) == 1
    assert data[0]["permission"] == "operator"


async def test_remove_permission_quita_y_publica() -> None:
    deps, storage, console, bus, _ = make_deps(ServerState.RUNNING)
    storage.write("permissions.json", b'[{"permission":"operator","xuid":"12345"}]\n')
    events: list[DomainEvent] = []
    bus.subscribe("player.operator_changed", events.append)
    await use_cases.remove_permission(deps, "srv-1", "12345")
    data = json.loads(storage.read("permissions.json"))
    assert len(data) == 0
    assert console.commands[0].command == "deop 12345"
    assert len(events) == 1


async def test_remove_permission_no_encontrado() -> None:
    deps, _, _, _, _ = make_deps()
    with pytest.raises(PermissionNotFoundError):
        await use_cases.remove_permission(deps, "srv-1", "00000")


async def test_list_permissions() -> None:
    deps, storage, _, _, _ = make_deps()
    storage.write(
        "permissions.json",
        b'[{"permission":"operator","xuid":"1"},{"permission":"visitor","xuid":"2"}]\n',
    )
    entries = await use_cases.list_permissions(deps, "srv-1")
    assert len(entries) == 2


async def test_list_permissions_vacio() -> None:
    deps, _, _, _, _ = make_deps()
    entries = await use_cases.list_permissions(deps, "srv-1")
    assert entries == []


# -- validación ---------------------------------------------------------------


async def test_add_to_allowlist_sin_name() -> None:
    deps, _, _, _, _ = make_deps()
    with pytest.raises(PermissionValidationError, match="name requerido"):
        await use_cases.add_to_allowlist(deps, "srv-1", "", "12345")


async def test_add_to_allowlist_sin_xuid() -> None:
    deps, _, _, _, _ = make_deps()
    with pytest.raises(PermissionValidationError, match="xuid requerido"):
        await use_cases.add_to_allowlist(deps, "srv-1", "Test", "")


async def test_set_permission_sin_xuid() -> None:
    deps, _, _, _, _ = make_deps()
    with pytest.raises(PermissionValidationError, match="xuid requerido"):
        await use_cases.set_permission_level(deps, "srv-1", "", PermissionLevel.OPERATOR)


async def test_remove_from_allowlist_sin_xuid() -> None:
    deps, _, _, _, _ = make_deps()
    with pytest.raises(PermissionValidationError, match="xuid requerido"):
        await use_cases.remove_from_allowlist(deps, "srv-1", "")


async def test_remove_permission_sin_xuid() -> None:
    deps, _, _, _, _ = make_deps()
    with pytest.raises(PermissionValidationError, match="xuid requerido"):
        await use_cases.remove_permission(deps, "srv-1", "")


# -- eventos (set/remove permission publican PLAYER_OPERATOR_CHANGED) ----------


async def test_set_permission_member_publica_operator_false() -> None:
    deps, _, _, bus, _ = make_deps()
    events: list[DomainEvent] = []
    bus.subscribe("player.operator_changed", events.append)
    await use_cases.set_permission_level(deps, "srv-1", "12345", PermissionLevel.MEMBER)
    assert events[0].payload["operator"] is False


async def test_set_permission_visitor_publica_operator_false() -> None:
    deps, _, _, bus, _ = make_deps()
    events: list[DomainEvent] = []
    bus.subscribe("player.operator_changed", events.append)
    await use_cases.set_permission_level(deps, "srv-1", "12345", PermissionLevel.VISITOR)
    assert events[0].payload["operator"] is False


async def test_remove_permission_publica_operator_false() -> None:
    deps, storage, _, bus, _ = make_deps()
    storage.write("permissions.json", b'[{"permission":"operator","xuid":"12345"}]\n')
    events: list[DomainEvent] = []
    bus.subscribe("player.operator_changed", events.append)
    await use_cases.remove_permission(deps, "srv-1", "12345")
    assert events[0].payload["operator"] is False
