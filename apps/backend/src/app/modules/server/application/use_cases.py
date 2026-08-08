"""Use cases del módulo Server (Blueprint §4.7, §6 ciclo de vida).

Cada use case recibe sus puertos vía ``ServerDeps``; nunca importa
infraestructura. Las transiciones de estado las valida la entidad (dominio);
los eventos ``SERVER.*`` se publican solo vía ``EventBusPort`` (ADR-001).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Collection
from contextlib import asynccontextmanager
from dataclasses import dataclass

from app.kernel.events.bus import EventBusPort
from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.runtime import RuntimeSpec, ServerRuntimePort, ServerState
from app.kernel.ports.settings import SettingsPort
from app.kernel.time import TimeProviderPort
from app.modules.server.application.commands import (
    ApplyConfigCommand,
    ChangeVersionCommand,
    CreateServerCommand,
    RemoveServerCommand,
    RestartServerCommand,
    StartServerCommand,
    StopServerCommand,
    UpdateResourcesCommand,
)
from app.modules.server.application.ports import ConfigurationReader, DesiredConfig
from app.modules.server.application.results import ServerView, connection_from_spec
from app.modules.server.application.spec_factory import RuntimeSpecFactory
from app.modules.server.domain.errors import (
    ServerBusyError,
    ServerNotMaterializedError,
    ServerResourcesValidationError,
    ServerStateError,
)
from app.modules.server.domain.events import (
    SERVER_CONFIG_CHANGED,
    SERVER_CRASHED,
    SERVER_CREATED,
    SERVER_REMOVED,
    SERVER_STARTED,
    SERVER_STARTING,
    SERVER_STOPPED,
    SERVER_STOPPING,
    SERVER_VERSION_CHANGED,
    server_event,
    server_resources_changed,
)
from app.modules.server.domain.repository import ServerRepositoryPort
from app.modules.server.domain.server import Server, ServerId


@dataclass(slots=True)
class ServerDeps:
    """Dependencias comunes de los use cases del módulo Server."""

    repository: ServerRepositoryPort
    runtime: ServerRuntimePort
    bus: EventBusPort
    ids: IdGeneratorPort
    time: TimeProviderPort
    settings: SettingsPort
    configuration: ConfigurationReader
    spec_factory: RuntimeSpecFactory


class OperationGuard:
    """Serializa operaciones compuestas por servidor (§6.4, §16.3).

    Un reinicio/recreación durante otro en curso se rechaza.
    """

    def __init__(self) -> None:
        self._in_flight: set[str] = set()

    @asynccontextmanager
    async def locked(self, server_id: str) -> AsyncIterator[None]:
        if server_id in self._in_flight:
            raise ServerStateError(
                f"Operación ya en curso sobre {server_id}",
                context={"server_id": server_id},
            )
        self._in_flight.add(server_id)
        try:
            yield
        finally:
            self._in_flight.discard(server_id)


def to_view(server: Server, settings: SettingsPort) -> ServerView:
    return ServerView(
        id=server.id.value,
        name=server.name,
        state=server.state,
        version=server.version,
        image_ref=server.image_ref,
        runtime_id=server.runtime_id,
        created_at=server.created_at,
        updated_at=server.updated_at,
        connection=connection_from_spec(server.spec, settings),
    )


class CreateServerUseCase:
    """Crea una instancia y materializa su artefacto (Blueprint §6.1)."""

    def __init__(self, deps: ServerDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: CreateServerCommand) -> ServerView:
        deps = self._deps
        server_id = deps.ids.new_id()
        now = deps.time.now()
        desired = await deps.configuration.desired_config(server_id)
        if cmd.version is not None:
            desired = DesiredConfig(
                version=cmd.version,
                environment=desired.environment,
                config_rev=desired.config_rev,
            )

        occupied = await _occupied_ports(deps.repository)
        spec = deps.spec_factory.render(server_id, cmd.name, desired, occupied_ports=occupied)

        server = Server(
            id=ServerId(server_id),
            name=cmd.name,
            spec=spec,
            state=ServerState.CREATED,
            created_at=now,
            updated_at=now,
        )
        await deps.repository.save(server)

        runtime_id = deps.runtime.materialize(spec)
        server.runtime_id = runtime_id
        await deps.repository.save(server)

        await deps.bus.publish(
            server_event(
                SERVER_CREATED,
                server_id,
                actor_id=cmd.actor_id,
                payload={"name": server.name, "version": server.version},
            )
        )
        return to_view(server, deps.settings)


class StartServerUseCase:
    """Arranca el proceso; el estado ``running`` lo confirma Monitoring (§6.2)."""

    def __init__(self, deps: ServerDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: StartServerCommand) -> ServerView:
        deps = self._deps
        server = await deps.repository.get_required(ServerId(cmd.server_id))
        server.request_start()

        if server.runtime_id is None:
            raise ServerNotMaterializedError(
                f"Servidor {cmd.server_id} sin artefacto materializado"
            )
        deps.runtime.start(server.runtime_id)

        await deps.repository.save(server)
        await deps.bus.publish(
            server_event(
                SERVER_STARTING,
                server.id.value,
                actor_id=cmd.actor_id,
            )
        )
        return to_view(server, deps.settings)


class MarkStartedUseCase:
    """Confirma arranque (monitoring/probe): ``starting`` → ``running``."""

    def __init__(self, deps: ServerDeps) -> None:
        self._deps = deps

    async def execute(self, server_id: str) -> ServerView:
        deps = self._deps
        server = await deps.repository.get_required(ServerId(server_id))
        server.mark_started()
        await deps.repository.save(server)
        await deps.bus.publish(server_event(SERVER_STARTED, server.id.value))
        return to_view(server, deps.settings)


class StopServerUseCase:
    """Parada ordenada síncrona (Blueprint §6.3)."""

    def __init__(self, deps: ServerDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: StopServerCommand) -> ServerView:
        deps = self._deps
        server = await deps.repository.get_required(ServerId(cmd.server_id))
        server.request_stop()

        if server.runtime_id is None:
            raise ServerNotMaterializedError(
                f"Servidor {cmd.server_id} sin artefacto materializado"
            )
        await deps.repository.save(server)
        await deps.bus.publish(
            server_event(
                SERVER_STOPPING,
                server.id.value,
                actor_id=cmd.actor_id,
            )
        )

        deps.runtime.stop(server.runtime_id, grace=cmd.grace)
        server.mark_stopped()
        await deps.repository.save(server)
        await deps.bus.publish(
            server_event(
                SERVER_STOPPED,
                server.id.value,
                actor_id=cmd.actor_id,
            )
        )
        return to_view(server, deps.settings)


class MarkCrashedUseCase:
    """Registra caída (watcher de runtime): cualquier estado → ``crashed``."""

    def __init__(self, deps: ServerDeps) -> None:
        self._deps = deps

    async def execute(self, server_id: str) -> ServerView:
        deps = self._deps
        server = await deps.repository.get_required(ServerId(server_id))
        server.mark_crashed()
        await deps.repository.save(server)
        await deps.bus.publish(server_event(SERVER_CRASHED, server.id.value))
        return to_view(server, deps.settings)


class RestartServerUseCase:
    """Reinicio como operación única serializada (§6.4)."""

    def __init__(self, deps: ServerDeps, guard: OperationGuard) -> None:
        self._deps = deps
        self._guard = guard

    async def execute(self, cmd: RestartServerCommand) -> ServerView:
        deps = self._deps
        async with self._guard.locked(cmd.server_id):
            server = await deps.repository.get_required(ServerId(cmd.server_id))
            if server.runtime_id is None:
                raise ServerNotMaterializedError(
                    f"Servidor {cmd.server_id} sin artefacto materializado"
                )
            if server.state in (ServerState.STARTING, ServerState.RUNNING, ServerState.STOPPING):
                if server.state is not ServerState.STOPPING:
                    server.request_stop()
                self._deps.runtime.stop(server.runtime_id, grace=cmd.grace)
                server.mark_stopped()
                await deps.repository.save(server)
                await deps.bus.publish(
                    server_event(SERVER_STOPPED, server.id.value, actor_id=cmd.actor_id)
                )
            elif server.state not in (ServerState.STOPPED, ServerState.CRASHED):
                raise ServerStateError(
                    f"No se puede reiniciar desde {server.state}",
                    context={"server_id": cmd.server_id, "state": server.state},
                )
            server.request_start()
            self._deps.runtime.start(server.runtime_id)
            await deps.repository.save(server)
            await deps.bus.publish(
                server_event(SERVER_STARTING, server.id.value, actor_id=cmd.actor_id)
            )
            return to_view(server, deps.settings)


class RemoveServerUseCase:
    """Eliminación: stop si corre, remove del runtime, soft delete (§6.6)."""

    def __init__(self, deps: ServerDeps, guard: OperationGuard) -> None:
        self._deps = deps
        self._guard = guard

    async def execute(self, cmd: RemoveServerCommand) -> None:
        deps = self._deps
        async with self._guard.locked(cmd.server_id):
            server = await deps.repository.get_required(ServerId(cmd.server_id))
            if server.runtime_id is not None and server.state in (
                ServerState.STARTING,
                ServerState.RUNNING,
                ServerState.STOPPING,
            ):
                deps.runtime.stop(server.runtime_id, grace=30)
            if server.runtime_id is not None:
                deps.runtime.remove(server.runtime_id, delete_data=cmd.delete_data)
            server.mark_removed()
            await deps.repository.save(server)
            await deps.bus.publish(
                server_event(
                    SERVER_REMOVED,
                    server.id.value,
                    actor_id=cmd.actor_id,
                )
            )


class ApplyConfigUseCase:
    """Aplica la config deseada (entrada ``CONFIG.CHANGED``, §3.2/§16.8).

    Re-renderiza el ``RuntimeSpec`` desde la config deseada y, si cambió,
    recrea el contenedor (parar → materialize → arrancar), serializado.
    No invoca a Configuration: solo lee su config deseada (unidireccional).
    """

    def __init__(self, deps: ServerDeps, guard: OperationGuard) -> None:
        self._deps = deps
        self._guard = guard

    async def execute(self, cmd: ApplyConfigCommand) -> ServerView:
        deps = self._deps
        async with self._guard.locked(cmd.server_id):
            server = await deps.repository.get_required(ServerId(cmd.server_id))
            desired = await deps.configuration.desired_config(cmd.server_id)
            if cmd.level_name is not None:
                desired = DesiredConfig(
                    version=desired.version,
                    environment={**desired.environment, "LEVEL_NAME": cmd.level_name},
                    config_rev=desired.config_rev,
                )
            if cmd.allow_list is not None:
                desired = DesiredConfig(
                    version=desired.version,
                    environment={
                        **desired.environment,
                        "ALLOW_LIST": "true" if cmd.allow_list else "false",
                    },
                    config_rev=desired.config_rev,
                )
            occupied = await _occupied_ports(deps.repository, exclude=server.id.value)
            new_spec = deps.spec_factory.render(
                server.id.value,
                server.name,
                desired,
                occupied_ports=occupied,
            )

            was_running = server.state in (ServerState.STARTING, ServerState.RUNNING)
            changed = _spec_changed(server.spec, new_spec)

            if changed:
                await _recreate(
                    deps,
                    server,
                    new_spec,
                    restart_if_running=was_running,
                    actor_id=cmd.actor_id,
                )

            if cmd.config_rev is not None:
                server.desired_config_rev = cmd.config_rev
                server.applied_config_rev = cmd.config_rev
            await deps.repository.save(server)
            await deps.bus.publish(
                server_event(
                    SERVER_CONFIG_CHANGED,
                    server.id.value,
                    actor_id=cmd.actor_id,
                    payload={"config_rev": cmd.config_rev},
                )
            )
            return to_view(server, deps.settings)


class ChangeVersionUseCase:
    """Cambia la versión de BDS y recrea el contenedor (§6.5)."""

    def __init__(self, deps: ServerDeps, guard: OperationGuard) -> None:
        self._deps = deps
        self._guard = guard

    async def execute(self, cmd: ChangeVersionCommand) -> ServerView:
        deps = self._deps
        async with self._guard.locked(cmd.server_id):
            server = await deps.repository.get_required(ServerId(cmd.server_id))
            was_running = server.state in (ServerState.STARTING, ServerState.RUNNING)
            desired = await deps.configuration.desired_config(cmd.server_id)
            desired = DesiredConfig(
                version=cmd.version,
                environment=desired.environment,
                config_rev=desired.config_rev,
            )
            occupied = await _occupied_ports(deps.repository, exclude=server.id.value)
            new_spec = deps.spec_factory.render(
                server.id.value, server.name, desired, occupied_ports=occupied
            )

            await _recreate(
                deps,
                server,
                new_spec,
                restart_if_running=was_running,
                actor_id=cmd.actor_id,
            )
            await deps.repository.save(server)
            await deps.bus.publish(
                server_event(
                    SERVER_VERSION_CHANGED,
                    server.id.value,
                    actor_id=cmd.actor_id,
                    payload={"version": cmd.version},
                )
            )
            return to_view(server, deps.settings)


class UpdateServerResourcesUseCase:
    """Actualiza CPU/RAM de un servidor existente y recrea el contenedor.

    Flujo: obtener servidor → validar estado (no ``starting``/``stopping``/
    ``removed``) → validar cotas (CPU ≥ 1, RAM ≥ 512 MB) → si no hay cambios,
    no-op → persistir nuevo spec → recrear el contenedor (parar → materialize →
    arrancar si corría) → publicar ``SERVER.RESOURCES_CHANGED``.
    """

    def __init__(self, deps: ServerDeps, guard: OperationGuard) -> None:
        self._deps = deps
        self._guard = guard

    async def execute(self, cmd: UpdateResourcesCommand) -> ServerView:
        deps = self._deps
        async with self._guard.locked(cmd.server_id):
            server = await deps.repository.get_required(ServerId(cmd.server_id))

            if server.state in (
                ServerState.STARTING,
                ServerState.STOPPING,
                ServerState.REMOVED,
            ):
                raise ServerBusyError(
                    f"No se pueden cambiar recursos desde {server.state}",
                    context={"server_id": cmd.server_id, "state": server.state},
                )

            self._validate(cmd)
            was_running = server.state in (ServerState.STARTING, ServerState.RUNNING)
            old_resources = dict(server.spec.resources)

            changed = server.change_resources(
                cpu_cores=cmd.cpu_cores,
                ram_mb=cmd.ram_mb,
            )
            if not changed:
                return to_view(server, deps.settings)

            await _recreate(
                deps,
                server,
                server.spec,
                restart_if_running=was_running,
                actor_id=cmd.actor_id,
            )
            await deps.repository.save(server)
            await deps.bus.publish(
                server_resources_changed(
                    server.id.value,
                    actor_id=cmd.actor_id,
                    old_resources=old_resources,
                    new_resources=dict(server.spec.resources),
                )
            )
            return to_view(server, deps.settings)

    @staticmethod
    def _validate(cmd: UpdateResourcesCommand) -> None:
        if cmd.cpu_cores is not None and cmd.cpu_cores < 1:
            raise ServerResourcesValidationError(
                "CPU cores debe ser al menos 1",
                context={"cpu_cores": cmd.cpu_cores},
            )
        if cmd.cpu_cores is not None and cmd.cpu_cores > 64:
            raise ServerResourcesValidationError(
                "CPU cores no puede superar 64",
                context={"cpu_cores": cmd.cpu_cores},
            )
        if cmd.ram_mb is not None and cmd.ram_mb < 512:
            raise ServerResourcesValidationError(
                "RAM debe ser al menos 512 MB",
                context={"ram_mb": cmd.ram_mb},
            )
        if cmd.ram_mb is not None and cmd.ram_mb > 65536:
            raise ServerResourcesValidationError(
                "RAM no puede superar 65536 MB",
                context={"ram_mb": cmd.ram_mb},
            )


async def _recreate(
    deps: ServerDeps,
    server: Server,
    new_spec: RuntimeSpec,
    *,
    restart_if_running: bool,
    actor_id: str | None,
) -> None:
    """Parar (si corre) → materialize nuevo spec → arrancar si tocaba (§6.5)."""
    if server.runtime_id is not None:
        if server.state in (ServerState.STARTING, ServerState.RUNNING, ServerState.STOPPING):
            deps.runtime.stop(server.runtime_id, grace=30)
        deps.runtime.remove(server.runtime_id, delete_data=False)
    runtime_id = deps.runtime.materialize(new_spec)
    server.update_spec(new_spec)
    server.runtime_id = runtime_id

    if restart_if_running:
        deps.runtime.start(runtime_id)
        server.state = ServerState.STARTING
        await deps.bus.publish(server_event(SERVER_STARTING, server.id.value, actor_id=actor_id))


async def _occupied_ports(
    repository: ServerRepositoryPort,
    *,
    exclude: str | None = None,
) -> Collection[int]:
    ports: set[int] = set()
    for other in await repository.list_all():
        if exclude is not None and other.id.value == exclude:
            continue
        if other.state is ServerState.REMOVED:
            continue
        ports.update(other.spec.ports.values())
    return ports


def _spec_changed(current: RuntimeSpec, new: RuntimeSpec) -> bool:
    return (
        current.image != new.image
        or current.tag != new.tag
        or current.version != new.version
        or current.environment != new.environment
        or current.ports != new.ports
        or current.volumes != new.volumes
        or current.resources != new.resources
    )
