"""Tests de los use cases del módulo Backup (Fase F paso 13).

Cubre crear (save hold/resume best-effort, artefacto + checksum), restaurar
(stop/start, pre-restore protegido, integridad, fallos que preservan el mundo),
prune (retención keep-last-N respetando protegidos) y validate (checksum +
manifiesto). Se usan dobles inyectados: storage local sobre ``tmp_path``,
``LocalBackupStore`` real, repositorio en memoria y facade Console con runtime
fake (mismo criterio que World/Player).
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO

import pytest

from app.infrastructure.backups.local import LocalBackupStore
from app.infrastructure.events.bus import InProcessEventBus
from app.infrastructure.storage.local import LocalServerStorage
from app.kernel.events.event import DomainEvent
from app.kernel.ports.backups import BackupStorePort
from app.kernel.ports.runtime import ServerState
from app.modules.backup.application.archive import build_backup_archive
from app.modules.backup.application.commands import (
    CreateBackupCommand,
    PruneBackupCommand,
    RestoreBackupCommand,
    ValidateBackupCommand,
)
from app.modules.backup.application.facade import BackupFacade
from app.modules.backup.application.results import BackupView
from app.modules.backup.application.use_cases import BackupDeps
from app.modules.backup.domain.backup import Backup, BackupState
from app.modules.backup.domain.errors import (
    BackupCorruptError,
    BackupNotFoundError,
    BackupValidationError,
)
from app.modules.backup.domain.events import (
    BACKUP_COMPLETED_TOPIC,
    BACKUP_DELETED_TOPIC,
    BACKUP_FAILED_TOPIC,
    BACKUP_RESTORE_COMPLETED_TOPIC,
    BACKUP_RESTORE_FAILED_TOPIC,
    BACKUP_RESTORE_STARTED_TOPIC,
    BACKUP_STARTED_TOPIC,
    BACKUP_VALIDATED_TOPIC,
)
from app.modules.backup.infrastructure.memory import InMemoryBackupRepository
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.streaming import ConsoleOutputRouter
from app.modules.console.application.use_cases import ConsoleDeps
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.server.application.commands import StartServerCommand, StopServerCommand
from app.modules.server.application.results import ServerView, stub_connection
from tests.conftest import FakeRuntime, FakeServerReader, FakeSettings, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SERVER_ID = "srv-1"


class Clock:
    """``TimeProviderPort`` con hora avanzable (para retención determinista)."""

    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta


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
    return ConsoleFacade(deps=deps, queue=queue, router=router)


def make_view(state: ServerState = ServerState.STOPPED) -> ServerView:
    return ServerView(
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


class FakeServerController:
    """``ServerController`` en memoria que registra stop/start (§8.6)."""

    def __init__(self, views: dict[str, ServerView]) -> None:
        self._views = dict(views)
        self.stops: list[str] = []
        self.starts: list[str] = []

    async def get_server(self, server_id: str) -> ServerView | None:
        return self._views.get(server_id)

    async def stop(self, cmd: StopServerCommand) -> ServerView:
        self.stops.append(cmd.server_id)
        return self._views[cmd.server_id]

    async def start(self, cmd: StartServerCommand) -> ServerView:
        self.starts.append(cmd.server_id)
        return self._views[cmd.server_id]


class FailingStore:
    """``BackupStorePort`` que falla al hacer ``put`` (simula disco lleno)."""

    def __init__(self, inner: BackupStorePort) -> None:
        self._inner = inner

    def put(self, ref: str, stream: BinaryIO) -> None:
        raise RuntimeError("disco lleno")

    def get(self, ref: str) -> BinaryIO:
        return self._inner.get(ref)

    def delete(self, ref: str) -> None:
        self._inner.delete(ref)

    def exists(self, ref: str) -> bool:
        return self._inner.exists(ref)

    def list(self, location: str | None = None) -> list[str]:
        return self._inner.list(location)

    def verify(self, ref: str, expected_checksum: str) -> bool:
        return self._inner.verify(ref, expected_checksum)


class Fixture:
    """Deps del módulo Backup con dobles (storage y store reales en tmp_path)."""

    def __init__(
        self,
        storage_root: Path,
        backup_root: Path,
        *,
        state: ServerState = ServerState.STOPPED,
        store: BackupStorePort | None = None,
    ) -> None:
        self.bus = InProcessEventBus()
        self.clock = Clock()
        self.repository = InMemoryBackupRepository()
        self.runtime = FakeRuntime()
        self.console = make_console(self.bus, self.clock, self.runtime, state=state)
        self.controller = FakeServerController({SERVER_ID: make_view(state)})
        local_store = LocalBackupStore(backup_root)
        self.store = local_store if store is None else store
        self.deps = BackupDeps(
            repository=self.repository,
            storage=TmpStorageResolver(storage_root),
            store=self.store,
            console=self.console,
            server=self.controller,
            bus=self.bus,
            ids=SequenceIds("bk-1", "bk-2", "bk-3", "bk-4", "bk-5"),
            time=self.clock,
            settings=FakeSettings(),
        )
        self.facade = BackupFacade(self.deps)
        self.facade.register_handlers()
        self.storage = self.deps.storage.for_server(SERVER_ID)

    def seed_world(self, name: str = "Alpha", *, content: bytes = b"\x0a\x00\x00") -> None:
        """Crea un mundo real en el storage (como si lo pusiera el volumen)."""
        self.storage.write(f"worlds/{name}/level.dat", content)
        self.storage.write(f"worlds/{name}/levelname.txt", name.encode("utf-8"))

    async def make_backup(self, name: str = "Alpha", *, protected: bool = False) -> BackupView:
        return await self.facade.create_backup(
            CreateBackupCommand(server_id=SERVER_ID, world_name=name, protected=protected)
        )

    async def save_record(self, backup: Backup) -> None:
        await self.repository.save_backup(backup)


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    return tmp_path / "storage"


@pytest.fixture
def backup_root(tmp_path: Path) -> Path:
    return tmp_path / "backups"


def make_zip(members: list[tuple[str, bytes]]) -> BinaryIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in members:
            zf.writestr(name, payload)
    buffer.seek(0)
    return buffer


def craft_artifact(fx: Fixture, name: str = "Alpha") -> tuple[str, str, list[str]]:
    """Guarda en el store un artefacto cuyo zip no contiene ``level.dat``."""
    zip_stream = make_zip([("no-level/foo.txt", b"basura")])
    archive = build_backup_archive(name, zip_stream)
    zip_stream.close()
    ref = f"{SERVER_ID}/bk-craft.tar.zst"
    fx.store.put(ref, archive.stream)
    archive.stream.close()
    return ref, archive.checksum, archive.entries


# -- crear -------------------------------------------------------------------


async def test_create_genera_artefacto_y_publica_completado(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root, state=ServerState.RUNNING)
    fx.seed_world()
    events: list[DomainEvent] = []
    fx.bus.subscribe(BACKUP_STARTED_TOPIC, events.append)
    fx.bus.subscribe(BACKUP_COMPLETED_TOPIC, events.append)

    view = await fx.make_backup()

    assert view.state == BackupState.COMPLETED.value
    assert view.size_bytes > 0
    assert view.checksum
    assert "level.dat" in view.entries
    assert fx.store.exists(f"{SERVER_ID}/{view.id}.tar.zst")
    assert fx.store.verify(f"{SERVER_ID}/{view.id}.tar.zst", view.checksum)

    writes = [data for _, data in fx.runtime.stdin_writes]
    assert "save hold\n" in writes
    assert "save resume\n" in writes
    assert writes.index("save hold\n") < writes.index("save resume\n")
    assert [e.type for e in events] == ["BACKUP.STARTED", "BACKUP.COMPLETED"]


async def test_create_en_stopped_no_envia_save_hold(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root, state=ServerState.STOPPED)
    fx.seed_world()

    view = await fx.make_backup()

    assert view.state == BackupState.COMPLETED.value
    assert fx.runtime.stdin_writes == []


async def test_create_de_mundo_inexistente_fracasa(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)

    with pytest.raises(BackupValidationError):
        await fx.facade.create_backup(CreateBackupCommand(server_id=SERVER_ID, world_name="Nope"))

    assert await fx.repository.list_backups(SERVER_ID) == []


@pytest.mark.parametrize(
    "name",
    ["", "  ", ".hidden", "..", "a/b", "a\\b", "x" * 256],
)
async def test_create_con_nombre_invalido_fracasa(
    storage_root: Path,
    backup_root: Path,
    name: str,
) -> None:
    fx = Fixture(storage_root, backup_root)

    with pytest.raises(BackupValidationError):
        await fx.facade.create_backup(CreateBackupCommand(server_id=SERVER_ID, world_name=name))


async def test_create_fallo_del_store_marca_failed(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root, state=ServerState.STOPPED)
    fx.seed_world()
    fx.store = FailingStore(fx.store)
    fx.deps.store = fx.store
    fx.facade = BackupFacade(fx.deps)
    events: list[DomainEvent] = []
    fx.bus.subscribe(BACKUP_STARTED_TOPIC, events.append)
    fx.bus.subscribe(BACKUP_FAILED_TOPIC, events.append)

    with pytest.raises(RuntimeError):
        await fx.make_backup()

    records = await fx.repository.list_backups(SERVER_ID)
    assert len(records) == 1
    assert records[0].state is BackupState.FAILED
    assert records[0].error == "disco lleno"
    assert [e.type for e in events] == ["BACKUP.STARTED", "BACKUP.FAILED"]


# -- restaurar ---------------------------------------------------------------


async def test_restore_restaura_el_mundo_y_publica(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root, state=ServerState.STOPPED)
    fx.seed_world(content=b"OLD")
    backup = await fx.make_backup()
    fx.storage.write("worlds/Alpha/level.dat", b"NEW")
    events: list[DomainEvent] = []
    fx.bus.subscribe(BACKUP_RESTORE_STARTED_TOPIC, events.append)
    fx.bus.subscribe(BACKUP_RESTORE_COMPLETED_TOPIC, events.append)

    await fx.facade.restore_backup(RestoreBackupCommand(backup_id=backup.id))

    assert fx.storage.read("worlds/Alpha/level.dat") == b"OLD"
    assert fx.controller.stops == []
    assert fx.controller.starts == []
    assert [e.type for e in events] == [
        "BACKUP.RESTORE_STARTED",
        "BACKUP.RESTORE_COMPLETED",
    ]


async def test_restore_publica_pre_restore_protegido(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    fx.seed_world()
    backup = await fx.make_backup()

    await fx.facade.restore_backup(RestoreBackupCommand(backup_id=backup.id))

    records = await fx.repository.list_backups(SERVER_ID)
    pre_restore = [b for b in records if b.id != backup.id]
    assert len(pre_restore) == 1
    assert pre_restore[0].protected is True
    assert pre_restore[0].state is BackupState.COMPLETED
    assert fx.store.exists(pre_restore[0].storage_ref)


async def test_restore_con_servidor_running_detiene_y_rearranca(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root, state=ServerState.RUNNING)
    fx.seed_world()
    backup = await fx.make_backup()

    await fx.facade.restore_backup(RestoreBackupCommand(backup_id=backup.id))

    assert fx.controller.stops == [SERVER_ID]
    assert fx.controller.starts == [SERVER_ID]
    assert fx.storage.exists("worlds/Alpha/level.dat")


async def test_restore_de_backup_desconocido_fracasa(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)

    with pytest.raises(BackupNotFoundError):
        await fx.facade.restore_backup(RestoreBackupCommand(backup_id="nope"))


async def test_restore_de_backup_no_completado_fracasa(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    await fx.save_record(
        Backup(
            id="bk-x",
            server_id=SERVER_ID,
            world_name="Alpha",
            state=BackupState.FAILED,
            storage_ref="srv-1/bk-x.tar.zst",
            created_at=NOW,
            updated_at=NOW,
        )
    )

    with pytest.raises(BackupValidationError):
        await fx.facade.restore_backup(RestoreBackupCommand(backup_id="bk-x"))


async def test_restore_sin_level_dat_fracasa_y_preserva_el_mundo(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    fx.seed_world(content=b"OLD")
    ref, checksum, entries = craft_artifact(fx)
    await fx.save_record(
        Backup(
            id="bk-craft",
            server_id=SERVER_ID,
            world_name="Alpha",
            state=BackupState.COMPLETED,
            storage_ref=ref,
            created_at=NOW,
            updated_at=NOW,
            size_bytes=1,
            checksum=checksum,
            entries=entries,
        )
    )
    events: list[DomainEvent] = []
    fx.bus.subscribe(BACKUP_RESTORE_STARTED_TOPIC, events.append)
    fx.bus.subscribe(BACKUP_RESTORE_FAILED_TOPIC, events.append)

    with pytest.raises(BackupCorruptError):
        await fx.facade.restore_backup(RestoreBackupCommand(backup_id="bk-craft"))

    assert fx.storage.read("worlds/Alpha/level.dat") == b"OLD"
    assert not fx.storage.exists("staging")
    assert [e.type for e in events] == [
        "BACKUP.RESTORE_STARTED",
        "BACKUP.RESTORE_FAILED",
    ]


async def test_restore_con_checksum_corrupto_marca_corrupt(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    fx.seed_world(content=b"OLD")
    backup = await fx.make_backup()
    fx.store.put(f"{SERVER_ID}/{backup.id}.tar.zst", io.BytesIO(b"basura"))

    with pytest.raises(BackupCorruptError):
        await fx.facade.restore_backup(RestoreBackupCommand(backup_id=backup.id))

    record = await fx.repository.get_backup(backup.id)
    assert record is not None and record.state is BackupState.CORRUPT
    assert fx.storage.read("worlds/Alpha/level.dat") == b"OLD"


# -- prune -------------------------------------------------------------------


async def test_prune_conserva_los_n_mas_recientes_y_borra_artefactos(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    fx.seed_world()
    first = await fx.make_backup()
    fx.clock.advance(timedelta(seconds=1))
    second = await fx.make_backup()
    fx.clock.advance(timedelta(seconds=1))
    third = await fx.make_backup()
    events: list[DomainEvent] = []
    fx.bus.subscribe(BACKUP_DELETED_TOPIC, events.append)

    deleted = await fx.facade.prune(PruneBackupCommand(server_id=SERVER_ID, keep_last_n=1))

    assert {d.id for d in deleted} == {first.id, second.id}
    assert [b.id for b in await fx.repository.list_backups(SERVER_ID)] == [third.id]
    assert not fx.store.exists(f"{SERVER_ID}/{first.id}.tar.zst")
    assert not fx.store.exists(f"{SERVER_ID}/{second.id}.tar.zst")
    assert fx.store.exists(f"{SERVER_ID}/{third.id}.tar.zst")
    assert [e.type for e in events] == ["BACKUP.DELETED", "BACKUP.DELETED"]


async def test_prune_no_borra_protegidos(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    fx.seed_world()
    normal = await fx.make_backup()
    fx.clock.advance(timedelta(seconds=1))
    protected = await fx.make_backup(protected=True)
    fx.clock.advance(timedelta(seconds=1))

    deleted = await fx.facade.prune(PruneBackupCommand(server_id=SERVER_ID, keep_last_n=1))

    assert deleted == []
    deleted = await fx.facade.prune(PruneBackupCommand(server_id=SERVER_ID, keep_last_n=0))
    assert [d.id for d in deleted] == [normal.id]
    assert [b.id for b in await fx.repository.list_backups(SERVER_ID)] == [protected.id]
    assert not fx.store.exists(f"{SERVER_ID}/{normal.id}.tar.zst")
    assert fx.store.exists(f"{SERVER_ID}/{protected.id}.tar.zst")


async def test_prune_con_keep_negativo_fracasa(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)

    with pytest.raises(BackupValidationError):
        await fx.facade.prune(PruneBackupCommand(server_id=SERVER_ID, keep_last_n=-1))


# -- validate ----------------------------------------------------------------


async def test_validate_ok_publica_validado(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    fx.seed_world()
    backup = await fx.make_backup()
    events: list[DomainEvent] = []
    fx.bus.subscribe(BACKUP_VALIDATED_TOPIC, events.append)

    view = await fx.facade.validate(ValidateBackupCommand(backup_id=backup.id))

    assert view.id == backup.id
    assert view.state == BackupState.COMPLETED.value
    assert [e.type for e in events] == ["BACKUP.VALIDATED"]


async def test_validate_con_checksum_corrupto_marca_corrupt(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    fx.seed_world()
    backup = await fx.make_backup()
    fx.store.put(f"{SERVER_ID}/{backup.id}.tar.zst", io.BytesIO(b"basura"))

    with pytest.raises(BackupCorruptError):
        await fx.facade.validate(ValidateBackupCommand(backup_id=backup.id))

    record = await fx.repository.get_backup(backup.id)
    assert record is not None and record.state is BackupState.CORRUPT
    assert record.error == "checksum"


async def test_validate_sin_level_dat_en_manifiesto_marca_corrupt(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    ref, checksum, entries = craft_artifact(fx)
    await fx.save_record(
        Backup(
            id="bk-craft",
            server_id=SERVER_ID,
            world_name="Alpha",
            state=BackupState.COMPLETED,
            storage_ref=ref,
            created_at=NOW,
            updated_at=NOW,
            size_bytes=1,
            checksum=checksum,
            entries=entries,
        )
    )

    with pytest.raises(BackupCorruptError):
        await fx.facade.validate(ValidateBackupCommand(backup_id="bk-craft"))

    record = await fx.repository.get_backup("bk-craft")
    assert record is not None and record.state is BackupState.CORRUPT


async def test_validate_de_backup_desconocido_fracasa(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)

    with pytest.raises(BackupNotFoundError):
        await fx.facade.validate(ValidateBackupCommand(backup_id="nope"))


# -- handlers ----------------------------------------------------------------


async def test_world_deleted_marca_huerfanos(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    fx.seed_world()
    backup = await fx.make_backup()

    await fx.bus.publish(
        DomainEvent(type="WORLD.DELETED", server_id=SERVER_ID, payload={"name": "Alpha"})
    )

    record = await fx.repository.get_backup(backup.id)
    assert record is not None and record.orphaned is True


async def test_world_deleted_defensivo_con_payload_invalido(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    fx.seed_world()
    backup = await fx.make_backup()

    await fx.bus.publish(DomainEvent(type="WORLD.DELETED", server_id=SERVER_ID, payload={}))

    record = await fx.repository.get_backup(backup.id)
    assert record is not None and record.orphaned is False


async def test_limite_max_backups_per_server_se_aplica(
    storage_root: Path,
    backup_root: Path,
) -> None:
    fx = Fixture(storage_root, backup_root)
    fx.deps.settings = FakeSettings({"limits.max_backups_per_server": 1})
    fx.seed_world()
    await fx.make_backup()
    with pytest.raises(BackupValidationError):
        await fx.make_backup()
