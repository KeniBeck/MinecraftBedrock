"""Tests de los use cases del módulo World (Fase E paso 12).

Cubre crear, importar (``.mcworld``), exportar con ``save hold``/``save
resume``, duplicar, eliminar (el activo no), activar (excluyente por
servidor) y reconciliar la metadata con el storage. Se usan dobles inyectados
(mismo criterio que Player/Console): storage local sobre ``tmp_path``,
repositorio en memoria y facade Console con runtime fake.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.infrastructure.storage.local import LocalServerStorage
from app.kernel.events.event import DomainEvent
from app.kernel.ports.runtime import ServerState
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.streaming import ConsoleOutputRouter
from app.modules.console.application.use_cases import ConsoleDeps
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.server.application.results import ServerView, stub_connection
from app.modules.world.application.commands import (
    ActivateWorldCommand,
    CreateWorldCommand,
    DeleteWorldCommand,
    DuplicateWorldCommand,
    ExportWorldCommand,
    ImportWorldCommand,
)
from app.modules.world.application.facade import WorldFacade
from app.modules.world.application.use_cases import (
    WorldDeps,
)
from app.modules.world.domain.errors import (
    WorldActiveError,
    WorldAlreadyExistsError,
    WorldCorruptError,
    WorldNotFoundError,
    WorldValidationError,
)
from app.modules.world.domain.events import (
    WORLD_ACTIVATED_TOPIC,
    WORLD_CREATED_TOPIC,
    WORLD_DELETED_TOPIC,
    WORLD_EXPORTED_TOPIC,
)
from app.modules.world.infrastructure.memory import InMemoryWorldRepository
from tests.conftest import FakeRuntime, FakeServerReader, FakeSettings, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SERVER_ID = "srv-1"


class Clock:
    """``TimeProviderPort`` con hora fija."""

    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class TmpStorageResolver:
    """``ServerStorageResolver`` sobre ``tmp_path`` (un subdir por servidor)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._cache: dict[str, LocalServerStorage] = {}

    def for_server(self, server_id: str) -> LocalServerStorage:
        storage = self._cache.get(server_id)
        if storage is None:
            storage = LocalServerStorage(self._root / server_id)
            self._cache[server_id] = storage
        return storage


def make_console(
    bus: InProcessEventBus,
    clock: Clock,
    runtime: FakeRuntime,
    *,
    state: ServerState = ServerState.RUNNING,
) -> ConsoleFacade:
    """Facade Console real con runtime fake; ``send_command`` exige RUNNING."""
    view = ServerView(
        id=SERVER_ID,
        name="Survival",
        state=state,
        version="1.20.0",
        image_ref="img:latest",
        runtime_id="r1",
        created_at=NOW,
        updated_at=NOW,
        connection=stub_connection(),
    )
    reader = FakeServerReader(views={SERVER_ID: view})
    deps = ConsoleDeps(
        server=reader,
        runtime=runtime,
        bus=bus,
        time=clock,
        settings=FakeSettings(),
        ids=SequenceIds("sub-1"),
        store=InMemoryConsoleLogStore(),
    )
    queue = CommandQueue(runtime=deps.runtime, bus=bus, time=clock)
    router = ConsoleOutputRouter(store=deps.store, bus=bus)
    console = ConsoleFacade(deps=deps, queue=queue, router=router)
    return console


class Fixture:
    """Deps del módulo World con dobles (storage real sobre tmp_path)."""

    def __init__(self, storage_root: Path, *, state: ServerState = ServerState.RUNNING) -> None:
        self.bus = InProcessEventBus()
        self.clock = Clock()
        self.repository = InMemoryWorldRepository()
        self.runtime = FakeRuntime()
        self.console = make_console(self.bus, self.clock, self.runtime, state=state)
        self.reader = self.console.deps.server
        self.deps = WorldDeps(
            repository=self.repository,
            storage=TmpStorageResolver(storage_root),
            console=self.console,
            server=self.reader,
            bus=self.bus,
            ids=SequenceIds("w-1", "w-2", "w-3", "w-4", "w-5"),
            time=self.clock,
        )
        self.facade = WorldFacade(self.deps)
        self.storage = self.deps.storage.for_server(SERVER_ID)

    def seed_world(self, name: str = "Alpha", *, level_name: str | None = None) -> None:
        """Crea un mundo real en el storage (como si lo pusiera el volumen)."""
        self.storage.write(f"worlds/{name}/level.dat", b"\x0a\x00\x00")
        self.storage.write(
            f"worlds/{name}/levelname.txt",
            (level_name or name).encode("utf-8"),
        )


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    return tmp_path / "storage"


def make_zip(members: list[tuple[str, bytes]]) -> BinaryIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in members:
            zf.writestr(name, payload)
    buffer.seek(0)
    return buffer


# -- crear -------------------------------------------------------------------


async def test_create_crea_metadata_y_levelname(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    events: list[DomainEvent] = []

    async def record(event: DomainEvent) -> None:
        events.append(event)

    fx.bus.subscribe(WORLD_CREATED_TOPIC, record)

    view = await fx.facade.create(CreateWorldCommand(server_id=SERVER_ID, name="Alpha"))

    assert view.name == "Alpha"
    assert view.level_name == "Alpha"
    assert view.activated is False
    assert fx.storage.read("worlds/Alpha/levelname.txt") == b"Alpha"
    assert [e.type for e in events] == ["WORLD.CREATED"]


async def test_create_con_nombre_duplicado_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")

    with pytest.raises(WorldAlreadyExistsError):
        await fx.facade.create(CreateWorldCommand(server_id=SERVER_ID, name="Alpha"))


@pytest.mark.parametrize(
    "name",
    ["", "  ", ".hidden", "..", "a/b", "a\\b", "x" * 256],
)
async def test_create_con_nombre_invalido_fracasa(storage_root: Path, name: str) -> None:
    fx = Fixture(storage_root)

    with pytest.raises(WorldValidationError):
        await fx.facade.create(CreateWorldCommand(server_id=SERVER_ID, name=name))


# -- importar -----------------------------------------------------------------


async def test_import_extrae_mcworld_con_envolvente(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    stream = make_zip(
        [
            ("MyWorld/level.dat", b"\x0a\x00\x00"),
            ("MyWorld/db/1.lbd", b"chunk"),
        ]
    )

    view = await fx.facade.import_world(
        ImportWorldCommand(server_id=SERVER_ID, name="Beta", stream=stream)
    )

    assert fx.storage.exists("worlds/Beta/level.dat")
    assert fx.storage.exists("worlds/Beta/db/1.lbd")
    assert view.level_name == "Beta"
    assert view.size_bytes > 0


async def test_import_sin_level_dat_limpia_y_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    stream = make_zip([("no-level/foo.txt", b"basura")])

    with pytest.raises(WorldCorruptError):
        await fx.facade.import_world(
            ImportWorldCommand(server_id=SERVER_ID, name="Beta", stream=stream)
        )

    assert not fx.storage.exists("worlds/Beta")


async def test_import_con_nombre_duplicado_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Beta")
    stream = make_zip([("Beta/level.dat", b"\x0a\x00\x00")])

    with pytest.raises(WorldAlreadyExistsError):
        await fx.facade.import_world(
            ImportWorldCommand(server_id=SERVER_ID, name="Beta", stream=stream)
        )


# -- exportar -----------------------------------------------------------------


async def test_export_en_running_manda_save_hold_y_save_resume(
    storage_root: Path,
) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    await fx.facade.sync(SERVER_ID)

    result = await fx.facade.export_world(ExportWorldCommand(server_id=SERVER_ID, name="Alpha"))

    writes = fx.runtime.stdin_writes
    assert ("r1", "save hold\n") in writes
    assert ("r1", "save resume\n") in writes
    assert writes.index(("r1", "save hold\n")) < writes.index(("r1", "save resume\n"))
    assert result.stream.read(2) == b"PK"
    assert result.size_bytes > 0
    result.stream.close()


async def test_export_en_stopped_no_envia_save_hold(storage_root: Path) -> None:
    fx = Fixture(storage_root, state=ServerState.STOPPED)
    fx.seed_world("Alpha")
    await fx.facade.sync(SERVER_ID)

    result = await fx.facade.export_world(ExportWorldCommand(server_id=SERVER_ID, name="Alpha"))

    assert fx.runtime.stdin_writes == []
    assert result.size_bytes > 0
    result.stream.close()


async def test_export_de_mundo_desconocido_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)

    with pytest.raises(WorldNotFoundError):
        await fx.facade.export_world(ExportWorldCommand(server_id=SERVER_ID, name="Nope"))


async def test_export_publica_world_exported(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    await fx.facade.sync(SERVER_ID)
    events: list[DomainEvent] = []
    fx.bus.subscribe(WORLD_EXPORTED_TOPIC, events.append)

    result = await fx.facade.export_world(ExportWorldCommand(server_id=SERVER_ID, name="Alpha"))

    result.stream.close()
    assert [e.type for e in events] == ["WORLD.EXPORTED"]


# -- duplicar -----------------------------------------------------------------


async def test_duplicate_clona_el_mundo_y_deja_el_origen(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")

    view = await fx.facade.duplicate(
        DuplicateWorldCommand(server_id=SERVER_ID, source="Alpha", target="AlphaCopy")
    )

    assert fx.storage.exists("worlds/AlphaCopy/level.dat")
    assert fx.storage.read("worlds/AlphaCopy/level.dat") == b"\x0a\x00\x00"
    assert fx.storage.exists("worlds/Alpha/level.dat")
    assert view.name == "AlphaCopy"
    assert view.activated is False


async def test_duplicate_con_origen_desconocido_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)

    with pytest.raises(WorldNotFoundError):
        await fx.facade.duplicate(
            DuplicateWorldCommand(server_id=SERVER_ID, source="Nope", target="X")
        )


async def test_duplicate_con_target_existente_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    fx.seed_world("AlphaCopy")

    with pytest.raises(WorldAlreadyExistsError):
        await fx.facade.duplicate(
            DuplicateWorldCommand(server_id=SERVER_ID, source="Alpha", target="AlphaCopy")
        )


# -- eliminar -----------------------------------------------------------------


async def test_delete_elimina_storage_metadata_y_publica(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    await fx.facade.create(CreateWorldCommand(server_id=SERVER_ID, name="Alpha"))
    events: list[DomainEvent] = []
    fx.bus.subscribe(WORLD_DELETED_TOPIC, events.append)

    await fx.facade.delete(DeleteWorldCommand(server_id=SERVER_ID, name="Alpha"))

    assert not fx.storage.exists("worlds/Alpha")
    assert await fx.repository.get_world(SERVER_ID, "Alpha") is None
    assert [e.type for e in events] == ["WORLD.DELETED"]


async def test_delete_del_mundo_activo_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    await fx.facade.create(CreateWorldCommand(server_id=SERVER_ID, name="Alpha"))
    await fx.facade.activate(ActivateWorldCommand(server_id=SERVER_ID, name="Alpha"))

    with pytest.raises(WorldActiveError):
        await fx.facade.delete(DeleteWorldCommand(server_id=SERVER_ID, name="Alpha"))

    assert fx.storage.exists("worlds/Alpha")


async def test_delete_de_mundo_desconocido_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)

    with pytest.raises(WorldNotFoundError):
        await fx.facade.delete(DeleteWorldCommand(server_id=SERVER_ID, name="Nope"))


# -- activar -------------------------------------------------------------------


async def test_activate_es_excluyente_y_publica_sin_config_rev(
    storage_root: Path,
) -> None:
    fx = Fixture(storage_root)
    await fx.facade.create(CreateWorldCommand(server_id=SERVER_ID, name="Alpha"))
    await fx.facade.create(CreateWorldCommand(server_id=SERVER_ID, name="Beta"))
    events: list[DomainEvent] = []
    fx.bus.subscribe(WORLD_ACTIVATED_TOPIC, events.append)

    await fx.facade.activate(ActivateWorldCommand(server_id=SERVER_ID, name="Alpha"))
    view = await fx.facade.activate(ActivateWorldCommand(server_id=SERVER_ID, name="Beta"))

    assert view.activated is True
    alpha = await fx.repository.get_world(SERVER_ID, "Alpha")
    assert alpha is not None and alpha.activated is False
    beta = await fx.repository.get_world(SERVER_ID, "Beta")
    assert beta is not None and beta.activated is True
    assert [e.type for e in events] == ["WORLD.ACTIVATED", "WORLD.ACTIVATED"]
    assert all("config_rev" not in e.payload for e in events)


async def test_activate_de_mundo_desconocido_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)

    with pytest.raises(WorldNotFoundError):
        await fx.facade.activate(ActivateWorldCommand(server_id=SERVER_ID, name="Nope"))


# -- reconciliar ----------------------------------------------------------------


async def test_sync_descubre_mundos_puestos_en_el_volumen(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")

    created = await fx.facade.sync(SERVER_ID)

    assert [v.name for v in created] == ["Alpha"]
    assert created[0].activated is False
    world = await fx.repository.get_world(SERVER_ID, "Alpha")
    assert world is not None and world.level_name == "Alpha"


async def test_sync_no_duplica_metadata_existente(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    await fx.facade.sync(SERVER_ID)
    await fx.facade.sync(SERVER_ID)

    worlds = await fx.repository.list_worlds(SERVER_ID)
    assert len(worlds) == 1


async def test_sync_refresca_size_bytes_de_mundos_conocidos(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    await fx.facade.sync(SERVER_ID)
    first = await fx.repository.get_world(SERVER_ID, "Alpha")
    assert first is not None

    fx.storage.write("worlds/Alpha/db/1.lbd", b"x" * 1024)
    reconciled = await fx.facade.sync(SERVER_ID)

    world = await fx.repository.get_world(SERVER_ID, "Alpha")
    assert world is not None
    assert world.size_bytes == first.size_bytes + 1024
    assert [v.name for v in reconciled] == ["Alpha"]
    assert reconciled[0].size_bytes == world.size_bytes


async def test_sync_preserva_identidad_y_activacion_al_refrescar(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    await fx.facade.sync(SERVER_ID)
    world = await fx.repository.get_world(SERVER_ID, "Alpha")
    assert world is not None
    await fx.facade.activate(ActivateWorldCommand(server_id=SERVER_ID, name="Alpha"))
    activated = await fx.repository.get_world(SERVER_ID, "Alpha")
    assert activated is not None and activated.activated is True

    fx.storage.write("worlds/Alpha/db/1.lbd", b"x" * 512)
    await fx.facade.sync(SERVER_ID)

    refreshed = await fx.repository.get_world(SERVER_ID, "Alpha")
    assert refreshed is not None
    assert refreshed.id == world.id
    assert refreshed.activated is True
    assert refreshed.created_at == world.created_at
    assert refreshed.updated_at >= activated.updated_at
    assert refreshed.size_bytes > world.size_bytes


async def test_sync_refresca_level_name_desde_el_disco(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha", level_name="Mundo")
    await fx.facade.sync(SERVER_ID)
    world = await fx.repository.get_world(SERVER_ID, "Alpha")
    assert world is not None and world.level_name == "Mundo"

    fx.storage.write("worlds/Alpha/levelname.txt", b"Renombrado")
    await fx.facade.sync(SERVER_ID)

    refreshed = await fx.repository.get_world(SERVER_ID, "Alpha")
    assert refreshed is not None and refreshed.level_name == "Renombrado"
