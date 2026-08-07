"""Facade pública del módulo Server (Blueprint §3.2: lifecycle, applyConfig,
changeVersion). Los consumidores usan esta facade, nunca la entidad.
"""

from __future__ import annotations

from app.modules.server.application.commands import (
    ApplyConfigCommand,
    ChangeVersionCommand,
    CreateServerCommand,
    RemoveServerCommand,
    RestartServerCommand,
    StartServerCommand,
    StopServerCommand,
)
from app.modules.server.application.handlers import (
    ConfigChangedHandler,
    WorldActivatedHandler,
)
from app.modules.server.application.ports import ConfigurationReader
from app.modules.server.application.queries import GetServerQuery, ListServersQuery
from app.modules.server.application.results import ServerView
from app.modules.server.application.spec_factory import RuntimeSpecFactory
from app.modules.server.application.use_cases import (
    ApplyConfigUseCase,
    ChangeVersionUseCase,
    CreateServerUseCase,
    MarkCrashedUseCase,
    MarkStartedUseCase,
    OperationGuard,
    RemoveServerUseCase,
    RestartServerUseCase,
    ServerDeps,
    StartServerUseCase,
    StopServerUseCase,
)
from app.modules.server.domain.events import (
    CONFIG_CHANGED_TOPIC,
    WORLD_ACTIVATED_TOPIC,
)
from app.modules.server.domain.repository import ServerRepositoryPort


class ServerFacade:
    """Puerta de entrada única al módulo Server (adapter-driven, sin IAM)."""

    def __init__(
        self,
        repository: ServerRepositoryPort,
        configuration: ConfigurationReader,
        spec_factory: RuntimeSpecFactory,
        deps: ServerDeps,
    ) -> None:
        self.repository = repository
        self.configuration = configuration
        self.spec_factory = spec_factory
        self.deps = deps
        self._guard = OperationGuard()
        self._create = CreateServerUseCase(self.deps)
        self._start = StartServerUseCase(self.deps)
        self._mark_started = MarkStartedUseCase(self.deps)
        self._stop = StopServerUseCase(self.deps)
        self._mark_crashed = MarkCrashedUseCase(self.deps)
        self._restart = RestartServerUseCase(self.deps, self._guard)
        self._remove = RemoveServerUseCase(self.deps, self._guard)
        self._apply_config = ApplyConfigUseCase(self.deps, self._guard)
        self._change_version = ChangeVersionUseCase(self.deps, self._guard)
        self._get = GetServerQuery(self.repository, self.deps.settings)
        self._list = ListServersQuery(self.repository, self.deps.settings)

    # -- lifecycle --------------------------------------------------------

    async def create(self, cmd: CreateServerCommand) -> ServerView:
        return await self._create.execute(cmd)

    async def start(self, cmd: StartServerCommand) -> ServerView:
        return await self._start.execute(cmd)

    async def stop(self, cmd: StopServerCommand) -> ServerView:
        return await self._stop.execute(cmd)

    async def restart(self, cmd: RestartServerCommand) -> ServerView:
        return await self._restart.execute(cmd)

    async def remove(self, cmd: RemoveServerCommand) -> None:
        await self._remove.execute(cmd)

    # -- confirmaciones (Monitoring / watcher de runtime) ------------------

    async def mark_started(self, server_id: str) -> ServerView:
        return await self._mark_started.execute(server_id)

    async def mark_crashed(self, server_id: str) -> ServerView:
        return await self._mark_crashed.execute(server_id)

    # -- config / versión --------------------------------------------------

    async def apply_config(self, cmd: ApplyConfigCommand) -> ServerView:
        return await self._apply_config.execute(cmd)

    async def change_version(self, cmd: ChangeVersionCommand) -> ServerView:
        return await self._change_version.execute(cmd)

    # -- consultas ----------------------------------------------------------

    async def get_server(self, server_id: str) -> ServerView | None:
        return await self._get.execute(server_id)

    async def list_servers(self) -> list[ServerView]:
        return await self._list.execute()

    # -- eventos ------------------------------------------------------------

    def register_handlers(self) -> None:
        """Suscriptores del módulo sobre el bus (Blueprint §3.2)."""
        self.deps.bus.subscribe(CONFIG_CHANGED_TOPIC, ConfigChangedHandler(self._apply_config))
        self.deps.bus.subscribe(WORLD_ACTIVATED_TOPIC, WorldActivatedHandler(self._apply_config))
