"""Use cases del módulo Backup (Blueprint §3.4, §7.4, §8).

Flujos sobre artefactos ``tar.zst`` (manifiesto + zip del mundo) en el
``BackupStorePort``:

- ``create``: snapshot del mundo con ``save hold``/``save resume`` best-effort
  si el servidor corre (mismo criterio que World export, §22), artefacto
  comprimido con checksum en streaming, registro y ``BACKUP.COMPLETED``.
- ``restore``: detiene el servidor, verifica integridad, extrae a **staging**,
  verifica ``level.dat``, hace snapshot **pre-restore** protegido y swap
  atómico (``staging → worlds/<nombre>``); si falla, rollback al pre-restore y
  servidor detenido (``BACKUP.RESTORE_FAILED``).
- ``prune``: retención keep-last-N por mundo (respeta ``protected``).
- ``validate``: checksum + manifiesto con ``level.dat`` (``BACKUP.VALIDATED``).

Backup no conoce el módulo World (matriz §1.3): el mundo se direcciona por el
nombre del directorio ``worlds/<nombre>`` (decisión §22; el §7.4 habla de
``world_id``, pero importarlo violaría la matriz de dependencias).
"""

from __future__ import annotations

import tarfile
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, BinaryIO

from app.kernel.events.bus import EventBusPort
from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.backups import BackupStorePort
from app.kernel.ports.runtime import ServerState
from app.kernel.ports.settings import SettingsPort
from app.kernel.ports.storage import ServerStoragePort
from app.kernel.time import TimeProviderPort
from app.modules.backup.application.archive import (
    BackupArchive,
    BackupArchiveReader,
    build_backup_archive,
)
from app.modules.backup.application.commands import (
    CreateBackupCommand,
    DeleteBackupCommand,
    PruneBackupCommand,
    RestoreBackupCommand,
    ValidateBackupCommand,
)
from app.modules.backup.application.ports import ServerController, ServerStorageResolver
from app.modules.backup.application.results import BackupView, backup_to_view
from app.modules.backup.domain.backup import Backup, BackupState
from app.modules.backup.domain.errors import (
    BackupCorruptError,
    BackupNotFoundError,
    BackupValidationError,
)
from app.modules.backup.domain.events import (
    BACKUP_COMPLETED,
    BACKUP_DELETED,
    BACKUP_FAILED,
    BACKUP_RESTORE_COMPLETED,
    BACKUP_RESTORE_FAILED,
    BACKUP_RESTORE_STARTED,
    BACKUP_STARTED,
    BACKUP_VALIDATED,
    backup_event,
)
from app.modules.backup.domain.repository import BackupRepositoryPort
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.domain.command import CommandPriority
from app.modules.console.domain.errors import ConsoleError
from app.modules.server.application.commands import StartServerCommand, StopServerCommand

_LEVEL_DAT = "level.dat"
_STAGING = "staging"


@dataclass(slots=True)
class BackupDeps:
    """Dependencias comunes de los use cases del módulo Backup."""

    repository: BackupRepositoryPort
    storage: ServerStorageResolver
    store: BackupStorePort
    console: ConsoleFacade
    server: ServerController
    bus: EventBusPort
    ids: IdGeneratorPort
    time: TimeProviderPort
    settings: SettingsPort


class CreateBackupUseCase:
    """Crea un backup manual/protegido de un mundo (Blueprint §8.1)."""

    def __init__(self, deps: BackupDeps) -> None:
        self._deps = deps

    async def create(self, cmd: CreateBackupCommand) -> BackupView:
        world_name = _clean_world_name(cmd.world_name)
        storage = self._deps.storage.for_server(cmd.server_id)
        if not storage.exists(f"worlds/{world_name}"):
            raise BackupValidationError(
                "El mundo no existe en el servidor",
                context={"server_id": cmd.server_id, "world_name": world_name},
            )

        started_at = self._deps.time.now()
        backup_id = self._deps.ids.new_id()
        ref = f"{cmd.server_id}/{backup_id}.tar.zst"
        record = Backup(
            id=backup_id,
            server_id=cmd.server_id,
            world_name=world_name,
            state=BackupState.RUNNING,
            storage_ref=ref,
            protected=cmd.protected,
            created_at=started_at,
            updated_at=started_at,
        )
        await self._deps.repository.save_backup(record)
        await self._deps.bus.publish(
            backup_event(
                BACKUP_STARTED,
                cmd.server_id,
                world_name,
                actor_id=cmd.actor_id,
                extra={"backup_id": backup_id},
            )
        )

        scope = f"backup:{cmd.server_id}"
        await storage.lock(scope)
        saved = False
        zip_stream: BinaryIO | None = None
        archive: BackupArchive | None = None
        error: BaseException | None = None
        try:
            if await _is_running(self._deps.server, cmd.server_id):
                await _best_effort_save(self._deps.console, cmd.server_id, "save hold")
                saved = True
            zip_stream = storage.world_snapshot(world_name)
            archive = build_backup_archive(world_name, zip_stream)
            self._deps.store.put(ref, archive.stream)
        except BaseException as exc:  # noqa: BLE001 — se normaliza abajo
            error = exc
        finally:
            if archive is not None:
                archive.stream.close()
            if zip_stream is not None:
                zip_stream.close()
            if saved:
                await _best_effort_save(self._deps.console, cmd.server_id, "save resume")
            await storage.unlock(scope)

        now = self._deps.time.now()
        if error is not None:
            await self._fail(record, error, now, actor_id=cmd.actor_id)
            raise error

        assert archive is not None
        duration = max(0, int((now - started_at).total_seconds()))
        completed = replace(
            record,
            state=BackupState.COMPLETED,
            size_bytes=archive.size_bytes,
            checksum=archive.checksum,
            entries=archive.entries,
            duration_seconds=duration,
            updated_at=now,
        )
        await self._deps.repository.save_backup(completed)
        await self._deps.bus.publish(
            backup_event(
                BACKUP_COMPLETED,
                cmd.server_id,
                world_name,
                actor_id=cmd.actor_id,
                extra={
                    "backup_id": backup_id,
                    "size_bytes": archive.size_bytes,
                    "checksum": archive.checksum,
                },
            )
        )
        return backup_to_view(completed)

    async def _fail(
        self,
        record: Backup,
        error: BaseException,
        now: datetime,
        *,
        actor_id: str | None,
    ) -> None:
        failed = replace(record, state=BackupState.FAILED, error=str(error), updated_at=now)
        await self._deps.repository.save_backup(failed)
        await self._deps.bus.publish(
            backup_event(
                BACKUP_FAILED,
                record.server_id,
                record.world_name,
                actor_id=actor_id,
                extra={"backup_id": record.id, "error": str(error)},
            )
        )


class RestoreBackupUseCase:
    """Restaura un backup sobre el mundo (§8.6), con pre-restore y rollback."""

    def __init__(self, deps: BackupDeps) -> None:
        self._deps = deps

    async def restore(self, cmd: RestoreBackupCommand) -> BackupView:
        backup = await self._deps.repository.get_backup(cmd.backup_id)
        if backup is None:
            raise BackupNotFoundError(
                "El registro de backup no existe",
                context={"backup_id": cmd.backup_id},
            )
        if backup.state is not BackupState.COMPLETED:
            raise BackupValidationError(
                "Solo se puede restaurar un backup completado",
                context={"backup_id": cmd.backup_id, "state": backup.state.value},
            )

        server_id = backup.server_id
        world_name = backup.world_name
        storage = self._deps.storage.for_server(server_id)
        await self._deps.bus.publish(
            backup_event(
                BACKUP_RESTORE_STARTED,
                server_id,
                world_name,
                actor_id=cmd.actor_id,
                extra={"backup_id": backup.id},
            )
        )

        view = await self._deps.server.get_server(server_id)
        was_running = view is not None and view.state is ServerState.RUNNING
        if was_running:
            await self._deps.server.stop(StopServerCommand(server_id=server_id))

        if not self._deps.store.verify(backup.storage_ref, backup.checksum):
            await self._mark_corrupt(backup, "checksum", actor_id=cmd.actor_id)
            raise BackupCorruptError(
                "El artefacto no supera la verificación de checksum",
                context={"backup_id": backup.id},
            )

        scope = f"backup:{server_id}"
        await storage.lock(scope)
        pre_ref: str | None = None
        swapped = False
        error: BaseException | None = None
        try:
            pre_ref = await self._stage_and_swap(backup, storage, server_id)
            swapped = True
        except BaseException as exc:  # noqa: BLE001 — rollback y normalización
            error = exc
        finally:
            await storage.unlock(scope)

        if error is not None:
            await self._rollback_if_needed(server_id, world_name, pre_ref, swapped)
            await self._deps.bus.publish(
                backup_event(
                    BACKUP_RESTORE_FAILED,
                    server_id,
                    world_name,
                    actor_id=cmd.actor_id,
                    extra={"backup_id": backup.id, "error": str(error)},
                )
            )
            raise error

        await self._deps.bus.publish(
            backup_event(
                BACKUP_RESTORE_COMPLETED,
                server_id,
                world_name,
                actor_id=cmd.actor_id,
                extra={"backup_id": backup.id},
            )
        )
        if was_running:
            await self._deps.server.start(StartServerCommand(server_id=server_id))
        return backup_to_view(backup)

    async def _stage_and_swap(
        self,
        backup: Backup,
        storage: ServerStoragePort,
        server_id: str,
    ) -> str | None:
        """Extrae a staging, hace pre-restore y swapea. Devuelve el ref del pre-restore."""
        reader = BackupArchiveReader(self._deps.store.get(backup.storage_ref))
        staging = f"{_STAGING}/{backup.id}"
        try:
            manifest = reader.manifest()
            _require_valid_manifest(manifest)
            world_zip = reader.world_zip()
            try:
                if storage.exists(staging):
                    storage.remove(staging)
                storage.write_snapshot(staging, world_zip)
            finally:
                world_zip.close()
        finally:
            reader.close()

        if not storage.exists(f"{staging}/{_LEVEL_DAT}"):
            raise BackupCorruptError(
                "El backup no contiene un nivel válido (sin level.dat)",
                context={"backup_id": backup.id},
            )

        pre_ref = None
        if storage.exists(f"worlds/{backup.world_name}"):
            pre_ref = await self._snapshot_pre_restore(storage, server_id, backup)

        storage.remove(f"worlds/{backup.world_name}")
        storage.move(staging, f"worlds/{backup.world_name}")
        return pre_ref

    async def _snapshot_pre_restore(
        self,
        storage: ServerStoragePort,
        server_id: str,
        source: Backup,
    ) -> str:
        now = self._deps.time.now()
        backup_id = self._deps.ids.new_id()
        ref = f"{server_id}/{backup_id}.tar.zst"
        zip_stream = storage.world_snapshot(source.world_name)
        try:
            archive = build_backup_archive(source.world_name, zip_stream)
        finally:
            zip_stream.close()
        self._deps.store.put(ref, archive.stream)
        archive.stream.close()
        pre = Backup(
            id=backup_id,
            server_id=server_id,
            world_name=source.world_name,
            state=BackupState.COMPLETED,
            storage_ref=ref,
            protected=True,
            size_bytes=archive.size_bytes,
            checksum=archive.checksum,
            entries=archive.entries,
            created_at=now,
            updated_at=now,
        )
        await self._deps.repository.save_backup(pre)
        return ref

    async def _rollback_if_needed(
        self,
        server_id: str,
        world_name: str,
        pre_ref: str | None,
        swapped: bool,
    ) -> None:
        """Restaña el pre-restore si el swap llegó a producirse (best-effort)."""
        if not swapped or pre_ref is None:
            return
        storage = self._deps.storage.for_server(server_id)
        scope = f"backup:{server_id}"
        await storage.lock(scope)
        try:
            reader = BackupArchiveReader(self._deps.store.get(pre_ref))
            staging = f"{_STAGING}/rollback-{self._deps.ids.new_id()}"
            try:
                world_zip = reader.world_zip()
                try:
                    if storage.exists(staging):
                        storage.remove(staging)
                    storage.write_snapshot(staging, world_zip)
                finally:
                    world_zip.close()
            finally:
                reader.close()
            storage.remove(f"worlds/{world_name}")
            storage.move(staging, f"worlds/{world_name}")
        finally:
            await storage.unlock(scope)

    async def _mark_corrupt(
        self,
        backup: Backup,
        reason: str,
        *,
        actor_id: str | None,
    ) -> None:
        now = self._deps.time.now()
        corrupt = replace(backup, state=BackupState.CORRUPT, error=reason, updated_at=now)
        await self._deps.repository.save_backup(corrupt)


class PruneBackupUseCase:
    """Limpieza por retención: conserva los N más recientes por mundo (§8.7)."""

    def __init__(self, deps: BackupDeps) -> None:
        self._deps = deps

    async def prune(self, cmd: PruneBackupCommand) -> list[BackupView]:
        if cmd.keep_last_n < 0:
            raise BackupValidationError(
                "keep_last_n no puede ser negativo",
                context={"keep_last_n": cmd.keep_last_n},
            )
        backups = await self._deps.repository.list_backups(cmd.server_id, limit=100000)
        by_world: dict[str, list[Backup]] = {}
        for backup in backups:
            by_world.setdefault(backup.world_name, []).append(backup)

        deleted: list[BackupView] = []
        for group in by_world.values():
            ordered = sorted(group, key=lambda item: item.created_at, reverse=True)
            kept = 0
            for backup in ordered:
                if backup.state is BackupState.DELETED or backup.protected:
                    continue
                if kept < cmd.keep_last_n:
                    kept += 1
                    continue
                self._deps.store.delete(backup.storage_ref)
                await self._deps.repository.delete_backup(backup.id)
                deleted.append(backup_to_view(backup))
                await self._deps.bus.publish(
                    backup_event(
                        BACKUP_DELETED,
                        cmd.server_id,
                        backup.world_name,
                        actor_id=cmd.actor_id,
                        extra={"backup_id": backup.id},
                    )
                )
        return deleted


class ValidateBackupUseCase:
    """Valida la integridad de un artefacto (checksum + manifiesto, §8.2)."""

    def __init__(self, deps: BackupDeps) -> None:
        self._deps = deps

    async def validate(self, cmd: ValidateBackupCommand) -> BackupView:
        backup = await self._deps.repository.get_backup(cmd.backup_id)
        if backup is None:
            raise BackupNotFoundError(
                "El registro de backup no existe",
                context={"backup_id": cmd.backup_id},
            )

        if not self._deps.store.verify(backup.storage_ref, backup.checksum):
            await self._mark_corrupt(backup, "checksum")
            raise BackupCorruptError(
                "El artefacto no supera la verificación de checksum",
                context={"backup_id": backup.id},
            )
        try:
            reader = BackupArchiveReader(self._deps.store.get(backup.storage_ref))
            try:
                manifest = reader.manifest()
                _require_valid_manifest(manifest)
            finally:
                reader.close()
        except (BackupCorruptError, OSError, tarfile.TarError) as exc:
            await self._mark_corrupt(backup, "manifest")
            raise BackupCorruptError(
                "El manifiesto del backup es inválido",
                context={"backup_id": backup.id, "error": str(exc)},
            ) from exc

        now = self._deps.time.now()
        ok = replace(backup, updated_at=now)
        await self._deps.repository.save_backup(ok)
        await self._deps.bus.publish(
            backup_event(
                BACKUP_VALIDATED,
                backup.server_id,
                backup.world_name,
                actor_id=cmd.actor_id,
                extra={"backup_id": backup.id},
            )
        )
        return backup_to_view(ok)

    async def _mark_corrupt(self, backup: Backup, reason: str) -> None:
        corrupt = replace(
            backup,
            state=BackupState.CORRUPT,
            error=reason,
            updated_at=self._deps.time.now(),
        )
        await self._deps.repository.save_backup(corrupt)


class DeleteBackupUseCase:
    """Elimina un backup individual: artefacto + registro + ``BACKUP.DELETED``.

    Los backups **protegidos** (pre-restore/pre-upgrade) no se pueden borrar
    manualmente: son el salvaguarda de operaciones que ya pasaron. El mismo
    criterio que ``PruneBackupUseCase``, que también los respeta (§8.7).
    """

    def __init__(self, deps: BackupDeps) -> None:
        self._deps = deps

    async def delete(self, cmd: DeleteBackupCommand) -> None:
        backup = await self._deps.repository.get_backup(cmd.backup_id)
        if backup is None:
            raise BackupNotFoundError(
                "El registro de backup no existe",
                context={"backup_id": cmd.backup_id},
            )
        if backup.protected:
            raise BackupValidationError(
                "El backup está protegido y no se puede eliminar",
                context={"backup_id": backup.id},
            )
        self._deps.store.delete(backup.storage_ref)
        await self._deps.repository.delete_backup(backup.id)
        await self._deps.bus.publish(
            backup_event(
                BACKUP_DELETED,
                backup.server_id,
                backup.world_name,
                actor_id=cmd.actor_id,
                extra={"backup_id": backup.id},
            )
        )


# -- helpers -----------------------------------------------------------------


def _clean_world_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or cleaned in (".", "..") or cleaned.startswith("."):
        raise BackupValidationError("Nombre de mundo inválido", context={"world_name": name})
    if any(separator in cleaned for separator in ("/", "\\")):
        raise BackupValidationError(
            "El nombre de mundo no puede contener separadores de ruta",
            context={"world_name": name},
        )
    if len(cleaned) > 255:
        raise BackupValidationError(
            "El nombre de mundo supera 255 caracteres",
            context={"world_name": name},
        )
    return cleaned


def _require_valid_manifest(manifest: dict[str, Any]) -> None:
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise BackupCorruptError("El manifiesto no lista entradas", context={"manifest": manifest})
    if _LEVEL_DAT not in entries:
        raise BackupCorruptError(
            "El manifiesto no incluye level.dat",
            context={"manifest": manifest},
        )


async def _is_running(server: ServerController, server_id: str) -> bool:
    view = await server.get_server(server_id)
    if view is None:
        return False
    return view.state is ServerState.RUNNING


async def _best_effort_save(console: ConsoleFacade, server_id: str, command: str) -> None:
    """Envía ``save hold``/``save resume``; fallos de Console se ignoran (§22)."""
    try:
        await console.send_command(
            SendCommand(
                server_id=server_id,
                command=command,
                priority=CommandPriority.HIGH,
            )
        )
    except ConsoleError:
        return
