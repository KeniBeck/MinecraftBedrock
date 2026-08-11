"""Use cases del módulo World (Blueprint §3.3, §4.2, §7.6).

Flujos sobre el árbol ``worlds/`` del storage del servidor (fuente de verdad =
filesystem vía ``ServerStoragePort``): crear, importar (``.mcworld``/tar.gz),
exportar (con ``save hold``/``save resume`` vía la facade Console si el
servidor corre), duplicar, eliminar y activar (excluyente por servidor). El
módulo exige ``level.dat`` como mínimo (validación NBT completa fuera de
alcance, §22); el sync lee los ajustes del mundo de forma **best effort**
(``seed``/``gamemode``/``difficulty`` del ``level.dat``, ``view_distance`` de
``server.properties``) para rellenar la metadata sin pisar lo configurado.

``WORLD.ACTIVATED`` lo publica World sin ``config_rev``; el handler de Server
lo trata como "reaplicar sin cambiar la revisión" (decisión §22).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, BinaryIO

from app.kernel.events.bus import EventBusPort
from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.runtime import ServerState
from app.kernel.ports.storage import ServerStoragePort
from app.kernel.time import TimeProviderPort
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.ports import ServerConsoleReader
from app.modules.console.domain.command import CommandPriority
from app.modules.console.domain.errors import ConsoleError
from app.modules.world.application.commands import (
    ActivateWorldCommand,
    CreateWorldCommand,
    DeleteWorldCommand,
    DuplicateWorldCommand,
    ExportWorldCommand,
    ImportWorldCommand,
    UpdateWorldCommand,
)
from app.modules.world.application.ports import ServerStorageResolver
from app.modules.world.application.results import (
    ExportWorldResult,
    WorldView,
    world_to_view,
)
from app.modules.world.domain.errors import (
    WorldActiveError,
    WorldAlreadyExistsError,
    WorldCorruptError,
    WorldNotFoundError,
    WorldValidationError,
)
from app.modules.world.domain.events import (
    WORLD_ACTIVATED,
    WORLD_CREATED,
    WORLD_DELETED,
    WORLD_DUPLICATED,
    WORLD_EXPORTED,
    WORLD_IMPORTED,
    WORLD_UPDATED,
    world_event,
)
from app.modules.world.domain.repository import WorldRepositoryPort
from app.modules.world.domain.world import World

_LEVEL_DAT = "level.dat"


@dataclass(slots=True)
class WorldDeps:
    """Dependencias comunes de los use cases del módulo World."""

    repository: WorldRepositoryPort
    storage: ServerStorageResolver
    console: ConsoleFacade
    server: ServerConsoleReader
    bus: EventBusPort
    ids: IdGeneratorPort
    time: TimeProviderPort


class CreateWorldUseCase:
    """Crea un mundo nuevo: metadata + directorio vacío con ``levelname.txt``.

    BDS genera el ``level.dat`` real en el primer arranque con ese level-name;
    el panel solo siembra el ``levelname.txt`` para que ``list_worlds`` lo vea.
    Los ajustes opcionales (seed/modo/dificultad/chunks) se guardan en la
    metadata y se inyectan como env al activar el mundo.
    """

    def __init__(self, deps: WorldDeps) -> None:
        self._deps = deps

    async def create(self, cmd: CreateWorldCommand) -> WorldView:
        name = _clean_name(cmd.name)
        storage = self._deps.storage.for_server(cmd.server_id)
        if storage.exists(f"worlds/{name}"):
            raise WorldAlreadyExistsError(
                "Ya existe un mundo con ese nombre",
                context={"server_id": cmd.server_id, "name": name},
            )
        storage.write(f"worlds/{name}/levelname.txt", name.encode("utf-8"))
        world = _new_world(
            self._deps,
            cmd.server_id,
            name,
            level_name=name,
            size_bytes=0,
            seed=cmd.seed,
            gamemode=cmd.gamemode,
            difficulty=cmd.difficulty,
            view_distance=cmd.view_distance,
        )
        await self._deps.repository.save_world(world)
        await self._deps.bus.publish(
            world_event(
                WORLD_CREATED,
                cmd.server_id,
                name,
                actor_id=cmd.actor_id,
                extra={"level_name": name, **_settings_extra(world)},
            )
        )
        return world_to_view(world)


class ImportWorldUseCase:
    """Importa un snapshot (``.mcworld``/tar.gz) como mundo nuevo.

    Valida que el nivel tenga ``level.dat`` (mínimo para considerar el mundo
    válido); si no, elimina lo extraído y falla con ``WORLD.CORRUPT``.
    """

    def __init__(self, deps: WorldDeps) -> None:
        self._deps = deps

    async def import_(self, cmd: ImportWorldCommand) -> WorldView:
        name = _clean_name(cmd.name)
        storage = self._deps.storage.for_server(cmd.server_id)
        rel = f"worlds/{name}"
        if storage.exists(rel):
            raise WorldAlreadyExistsError(
                "Ya existe un mundo con ese nombre",
                context={"server_id": cmd.server_id, "name": name},
            )
        storage.write_snapshot(rel, cmd.stream)
        if not storage.exists(f"{rel}/{_LEVEL_DAT}"):
            storage.remove(rel)
            raise WorldCorruptError(
                "El snapshot no contiene un nivel válido (sin level.dat)",
                context={"server_id": cmd.server_id, "name": name},
            )
        meta = _storage_meta(storage, name)
        world = _new_world(
            self._deps,
            cmd.server_id,
            name,
            level_name=meta["level_name"] if meta else name,
            size_bytes=meta["size_bytes"] if meta else 0,
        )
        await self._deps.repository.save_world(world)
        await self._deps.bus.publish(
            world_event(
                WORLD_IMPORTED,
                cmd.server_id,
                name,
                actor_id=cmd.actor_id,
                extra={"level_name": world.level_name, "size_bytes": world.size_bytes},
            )
        )
        return world_to_view(world)


class ExportWorldUseCase:
    """Exporta un mundo a snapshot zip, con ``save hold``/``save resume``.

    Si el servidor corre, pide ``save hold`` a BDS antes de empaquetar y
    ``save resume`` al terminar, bajo el lock del storage del servidor (evita
    dos exportaciones intercaladas). Los comandos de save son **best-effort**:
    si Console los rechaza (servidor parado a mitad, comando no soportado) se
    exporta igual y se documenta (el snapshot puede quedar menos consistente).
    """

    def __init__(self, deps: WorldDeps) -> None:
        self._deps = deps

    async def export(self, cmd: ExportWorldCommand) -> ExportWorldResult:
        name = _clean_name(cmd.name)
        storage = self._deps.storage.for_server(cmd.server_id)
        world = await self._deps.repository.get_world(cmd.server_id, name)
        if world is None:
            raise WorldNotFoundError(
                "El mundo no existe en el servidor",
                context={"server_id": cmd.server_id, "name": name},
            )

        scope = f"world:{cmd.server_id}"
        await storage.lock(scope)
        stream: BinaryIO | None = None
        running = await _is_running(self._deps.server, cmd.server_id)
        held = False
        try:
            if running:
                held = await _best_effort_save(self._deps.console, cmd.server_id, "save hold")
            stream = storage.world_snapshot(name)
        finally:
            if held:
                await _best_effort_save(self._deps.console, cmd.server_id, "save resume")
            await storage.unlock(scope)

        assert stream is not None
        size_bytes = _stream_size(stream)
        await self._deps.bus.publish(
            world_event(
                WORLD_EXPORTED,
                cmd.server_id,
                name,
                actor_id=cmd.actor_id,
                extra={"size_bytes": size_bytes, "consistent": not running or held},
            )
        )
        return ExportWorldResult(
            world=world_to_view(world),
            stream=stream,
            size_bytes=size_bytes,
            consistent=not running or held,
        )


class DuplicateWorldUseCase:
    """Clona un mundo existente a un nombre nuevo (snapshot → restauración)."""

    def __init__(self, deps: WorldDeps) -> None:
        self._deps = deps

    async def duplicate(self, cmd: DuplicateWorldCommand) -> WorldView:
        source = _clean_name(cmd.source)
        target = _clean_name(cmd.target)
        storage = self._deps.storage.for_server(cmd.server_id)
        if not storage.exists(f"worlds/{source}"):
            raise WorldNotFoundError(
                "El mundo origen no existe en el servidor",
                context={"server_id": cmd.server_id, "name": source},
            )
        if storage.exists(f"worlds/{target}"):
            raise WorldAlreadyExistsError(
                "Ya existe un mundo con ese nombre",
                context={"server_id": cmd.server_id, "name": target},
            )

        scope = f"world:{cmd.server_id}"
        await storage.lock(scope)
        try:
            source_stream = storage.world_snapshot(source)
            try:
                storage.write_snapshot(f"worlds/{target}", source_stream)
            finally:
                source_stream.close()
        finally:
            await storage.unlock(scope)

        if not storage.exists(f"worlds/{target}/{_LEVEL_DAT}"):
            storage.remove(f"worlds/{target}")
            raise WorldCorruptError(
                "El mundo origen no es un nivel válido (sin level.dat)",
                context={"server_id": cmd.server_id, "name": source},
            )
        meta = _storage_meta(storage, target)
        world = _new_world(
            self._deps,
            cmd.server_id,
            target,
            level_name=meta["level_name"] if meta else target,
            size_bytes=meta["size_bytes"] if meta else 0,
        )
        await self._deps.repository.save_world(world)
        await self._deps.bus.publish(
            world_event(
                WORLD_DUPLICATED,
                cmd.server_id,
                target,
                actor_id=cmd.actor_id,
                extra={"source": source},
            )
        )
        return world_to_view(world)


class DeleteWorldUseCase:
    """Elimina un mundo del storage y de la metadata.

    El mundo **activo** no se puede eliminar: el servidor puede estar corriendo
    con ese level-name (``WORLD.ACTIVE_IN_USE``). Primero hay que activar otro.
    """

    def __init__(self, deps: WorldDeps) -> None:
        self._deps = deps

    async def delete(self, cmd: DeleteWorldCommand) -> None:
        name = _clean_name(cmd.name)
        storage = self._deps.storage.for_server(cmd.server_id)
        world = await self._deps.repository.get_world(cmd.server_id, name)
        if world is None:
            raise WorldNotFoundError(
                "El mundo no existe en el servidor",
                context={"server_id": cmd.server_id, "name": name},
            )
        if world.activated:
            raise WorldActiveError(
                "El mundo activo no se puede eliminar (activa otro primero)",
                context={"server_id": cmd.server_id, "name": name},
            )

        scope = f"world:{cmd.server_id}"
        await storage.lock(scope)
        try:
            storage.remove(f"worlds/{name}")
            await self._deps.repository.delete_world(cmd.server_id, name)
        finally:
            await storage.unlock(scope)
        await self._deps.bus.publish(
            world_event(WORLD_DELETED, cmd.server_id, name, actor_id=cmd.actor_id)
        )


class ActivateWorldUseCase:
    """Activa un mundo (excluyente) y publica ``WORLD.ACTIVATED``.

    El handler de Server reaplica la config (level-name + ajustes) sin tocar la
    revisión de Configuration (el payload no lleva ``config_rev``, decisión §22).
    Los ajustes opcionales del mundo viajan en el payload para que el handler
    los inyecte como env (``LEVEL_SEED``/``GAMEMODE``/``DIFFICULTY``/``VIEW_DISTANCE``).
    """

    def __init__(self, deps: WorldDeps) -> None:
        self._deps = deps

    async def activate(self, cmd: ActivateWorldCommand) -> WorldView:
        name = _clean_name(cmd.name)
        storage = self._deps.storage.for_server(cmd.server_id)
        world = await self._deps.repository.get_world(cmd.server_id, name)
        if world is None or not storage.exists(f"worlds/{name}"):
            raise WorldNotFoundError(
                "El mundo no existe en el servidor",
                context={"server_id": cmd.server_id, "name": name},
            )
        await self._deps.repository.deactivate_worlds(cmd.server_id)
        activated = replace(world, activated=True, updated_at=self._deps.time.now())
        await self._deps.repository.save_world(activated)
        await self._deps.bus.publish(
            world_event(
                WORLD_ACTIVATED,
                cmd.server_id,
                name,
                actor_id=cmd.actor_id,
                extra={"level_name": activated.level_name, **_settings_extra(activated)},
            )
        )
        return world_to_view(activated)


class UpdateWorldUseCase:
    """Renombra y/o ajusta la configuración de un mundo existente.

    Si cambia el nombre: mueve ``worlds/<name>`` → ``worlds/<new_name>``,
    reescribe el ``levelname.txt`` y actualiza la metadata (identidad cambia).
    Los ajustes opcionales se actualizan solo si vienen en el comando.
    Si el mundo está **activo**, se re-publica ``WORLD.ACTIVATED`` con el nuevo
    nombre y los ajustes para que Server reaplique la config (level-name) sin
    cambiar la revisión de Configuration. En cualquier caso se publica
    ``WORLD.UPDATED`` (auditoría).
    """

    def __init__(self, deps: WorldDeps) -> None:
        self._deps = deps

    async def update(self, cmd: UpdateWorldCommand) -> WorldView:
        deps = self._deps
        storage = deps.storage.for_server(cmd.server_id)
        world = await deps.repository.get_world(cmd.server_id, cmd.name)
        if world is None or not storage.exists(f"worlds/{cmd.name}"):
            raise WorldNotFoundError(
                "El mundo no existe en el servidor",
                context={"server_id": cmd.server_id, "name": cmd.name},
            )

        target = _clean_name(cmd.new_name) if cmd.new_name else world.name
        if target != world.name:
            if storage.exists(f"worlds/{target}"):
                raise WorldAlreadyExistsError(
                    "Ya existe un mundo con ese nombre",
                    context={"server_id": cmd.server_id, "name": target},
                )
            storage.move(f"worlds/{world.name}", f"worlds/{target}")
            storage.write(f"worlds/{target}/levelname.txt", target.encode("utf-8"))

        updated = replace(
            world,
            name=target,
            level_name=target if target != world.name else world.level_name,
            seed=cmd.seed if cmd.seed is not None else world.seed,
            gamemode=cmd.gamemode if cmd.gamemode is not None else world.gamemode,
            difficulty=cmd.difficulty if cmd.difficulty is not None else world.difficulty,
            view_distance=(
                cmd.view_distance if cmd.view_distance is not None else world.view_distance
            ),
            updated_at=deps.time.now(),
        )

        if target != world.name:
            await deps.repository.delete_world(cmd.server_id, world.name)
        await deps.repository.save_world(updated)

        renamed = target != world.name
        await deps.bus.publish(
            world_event(
                WORLD_UPDATED,
                cmd.server_id,
                target,
                actor_id=cmd.actor_id,
                extra={
                    "renamed": renamed,
                    "previous_name": world.name if renamed else None,
                    **_settings_extra(updated),
                },
            )
        )
        if updated.activated:
            await deps.bus.publish(
                world_event(
                    WORLD_ACTIVATED,
                    cmd.server_id,
                    target,
                    actor_id=cmd.actor_id,
                    extra={"level_name": updated.level_name, **_settings_extra(updated)},
                )
            )
        return world_to_view(updated)


class ScanWorldsUseCase:
    """Reconcilia la metadata con el storage (mundos puestos a mano en el volumen).

    Para cada directorio de ``worlds/`` con ``level.dat``: si el panel aún no lo
    conoce, crea su metadata (``activated=False``); si ya existe, refresca los
    campos derivables del disco (``level_name``, ``size_bytes``, ``updated_at``)
    preservando identidad, activación y fechas de creación. En ambos casos
    rellena los ajustes del mundo (``seed``/``gamemode``/``difficulty``/
    ``view_distance``) leídos del disco cuando la metadata no los tiene
    (backfill: lo configurado por el usuario no se pisa). Devuelve el listado
    reconciliado. No borra metadata de mundos que ya no están en el disco (el
    borrado pasa por ``DeleteWorldUseCase``).
    """

    def __init__(self, deps: WorldDeps) -> None:
        self._deps = deps

    async def sync(self, server_id: str) -> list[WorldView]:
        storage = self._deps.storage.for_server(server_id)
        known = {world.name: world for world in await self._deps.repository.list_worlds(server_id)}
        reconciled: list[WorldView] = []
        for meta in storage.list_worlds():
            name = meta["name"]
            settings = storage.world_settings(name)
            world = known.get(name)
            if world is None:
                world = _new_world(
                    self._deps,
                    server_id,
                    name,
                    level_name=meta["level_name"],
                    size_bytes=meta["size_bytes"],
                    seed=settings.get("seed"),
                    gamemode=settings.get("gamemode"),
                    difficulty=settings.get("difficulty"),
                    view_distance=settings.get("view_distance"),
                )
                await self._deps.repository.save_world(world)
            else:
                refreshed = _refreshed_world(
                    world,
                    level_name=meta["level_name"],
                    size_bytes=meta["size_bytes"],
                    settings=settings,
                    now=self._deps.time.now(),
                )
                if refreshed is not world:
                    await self._deps.repository.save_world(refreshed)
                    world = refreshed
            reconciled.append(world_to_view(world))
        return reconciled


# -- helpers -----------------------------------------------------------------


def _refreshed_world(
    world: World,
    *,
    level_name: str,
    size_bytes: int,
    settings: dict[str, Any],
    now: datetime,
) -> World:
    """Copia de ``world`` con campos del disco; rellena ajustes aún vacíos.

    Los ajustes leídos del disco (``seed``/``gamemode``/``difficulty``/
    ``view_distance``) solo se copian si la metadata **no** los tiene aún
    (backfill): un valor que el panel ya configuró no se pisa. Devuelve la
    misma instancia si nada cambió.
    """
    seed = world.seed if world.seed is not None else settings.get("seed")
    gamemode = world.gamemode if world.gamemode is not None else settings.get("gamemode")
    difficulty = (
        world.difficulty if world.difficulty is not None else settings.get("difficulty")
    )
    view_distance = (
        world.view_distance
        if world.view_distance is not None
        else settings.get("view_distance")
    )
    if (
        world.level_name == level_name
        and world.size_bytes == size_bytes
        and seed == world.seed
        and gamemode == world.gamemode
        and difficulty == world.difficulty
        and view_distance == world.view_distance
    ):
        return world
    return replace(
        world,
        level_name=level_name,
        size_bytes=size_bytes,
        seed=seed,
        gamemode=gamemode,
        difficulty=difficulty,
        view_distance=view_distance,
        updated_at=now,
    )


def _new_world(
    deps: WorldDeps,
    server_id: str,
    name: str,
    *,
    level_name: str,
    size_bytes: int,
    seed: str | None = None,
    gamemode: str | None = None,
    difficulty: str | None = None,
    view_distance: int | None = None,
) -> World:
    now = deps.time.now()
    return World(
        id=deps.ids.new_id(),
        server_id=server_id,
        name=name,
        level_name=level_name,
        size_bytes=size_bytes,
        activated=False,
        created_at=now,
        updated_at=now,
        seed=seed,
        gamemode=gamemode,
        difficulty=difficulty,
        view_distance=view_distance,
    )


def _settings_extra(world: World) -> dict[str, object]:
    """Ajustes opcionales no-nulos para los payloads de eventos ``WORLD.*``."""
    extra: dict[str, object] = {}
    if world.seed is not None:
        extra["seed"] = world.seed
    if world.gamemode is not None:
        extra["gamemode"] = world.gamemode
    if world.difficulty is not None:
        extra["difficulty"] = world.difficulty
    if world.view_distance is not None:
        extra["view_distance"] = world.view_distance
    return extra


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or cleaned in (".", "..") or cleaned.startswith("."):
        raise WorldValidationError("Nombre de mundo inválido", context={"name": name})
    if any(separator in cleaned for separator in ("/", "\\")):
        raise WorldValidationError(
            "El nombre de mundo no puede contener separadores de ruta",
            context={"name": name},
        )
    if len(cleaned) > 255:
        raise WorldValidationError(
            "El nombre de mundo supera 255 caracteres",
            context={"name": name},
        )
    return cleaned


def _storage_meta(storage: ServerStoragePort, name: str) -> dict[str, Any] | None:
    for entry in storage.list_worlds():
        if entry["name"] == name:
            return entry
    return None


async def _is_running(server: ServerConsoleReader, server_id: str) -> bool:
    view = await server.get_server(server_id)
    if view is None:
        return False
    return view.state is ServerState.RUNNING


async def _best_effort_save(console: ConsoleFacade, server_id: str, command: str) -> bool:
    """Envía ``save hold``/``save resume``; fallos de Console se ignoran (§22).

    Devuelve ``True`` si Console aceptó el comando, ``False`` si lo rechazó
    (servidor parado a mitad, comando no soportado); el snapshot best-effort
    se exporta igual y queda marcado como ``consistent=False``.
    """
    try:
        await console.send_command(
            SendCommand(
                server_id=server_id,
                command=command,
                priority=CommandPriority.HIGH,
            )
        )
    except ConsoleError:
        return False
    return True


def _stream_size(stream: BinaryIO) -> int:
    position = stream.tell()
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(position)
    return size
