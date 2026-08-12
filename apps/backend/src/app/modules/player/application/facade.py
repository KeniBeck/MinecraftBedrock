"""Facade pública del módulo Player (Blueprint §3.5: resolveXuid, findPlayer).

Superficie pública: ``resolve_xuid(name)`` (gamertag → XUID cacheado),
``find_player(xuid)``, sesiones/presencia (``list_sessions``,
``online_players``), bans persistentes (globales y por servidor, ADR-011) y
expulsión vía Console (``kick``). Las operaciones de sesión/presencia se
conducen por eventos (handlers) en el lado de escritura; la facade solo expone
la consulta. Los bans viven en la capa de aplicación y se exponen aquí para el
paso de API (§16).
"""

from __future__ import annotations

from app.kernel.events.bus import EventBusPort
from app.modules.console.application.results import CommandAck
from app.modules.player.application.commands import (
    BanPlayerGloballyCommand,
    BanPlayerOnServerCommand,
    KickPlayerCommand,
    UnbanPlayerGloballyCommand,
    UnbanPlayerOnServerCommand,
)
from app.modules.player.application.handlers import (
    SERVER_STARTED_TOPIC,
    BanEnforcementHandler,
    OperatorChangedHandler,
    PlayerJoinedHandler,
    PlayerLeftHandler,
    ServerStartedHandler,
)
from app.modules.player.application.results import (
    GlobalBanView,
    PlayerView,
    PlaySessionView,
    ServerBanView,
    global_ban_to_view,
    player_to_view,
    server_ban_to_view,
    session_to_view,
)
from app.modules.player.application.use_cases import (
    BanPlayerGloballyUseCase,
    BanPlayerOnServerUseCase,
    CleanPresenceUseCase,
    JoinPlayerUseCase,
    KickPlayerUseCase,
    LeavePlayerUseCase,
    PlayerDeps,
    ResolvePlayerUseCase,
    UnbanPlayerGloballyUseCase,
    UnbanPlayerOnServerUseCase,
)
from app.modules.player.domain.events import (
    PLAYER_JOINED_TOPIC,
    PLAYER_LEFT_TOPIC,
    PLAYER_OPERATOR_CHANGED_TOPIC,
)


class PlayerFacade:
    """Puerta de entrada del módulo Player (lectura + gestión + handlers)."""

    def __init__(self, deps: PlayerDeps) -> None:
        self.deps = deps
        self._resolve = ResolvePlayerUseCase(deps)
        self._join = JoinPlayerUseCase(deps)
        self._leave = LeavePlayerUseCase(deps)
        self._clean = CleanPresenceUseCase(deps)
        self._kick = KickPlayerUseCase(deps)
        self._ban_global = BanPlayerGloballyUseCase(deps)
        self._unban_global = UnbanPlayerGloballyUseCase(deps)
        self._ban_server = BanPlayerOnServerUseCase(deps)
        self._unban_server = UnbanPlayerOnServerUseCase(deps)

    async def resolve_xuid(self, name: str) -> str | None:
        """Devuelve el XUID cacheado para un gamertag (o ``None`` si es desconocido)."""
        player = await self.deps.repository.get_player_by_name(name)
        return player.xuid if player is not None else None

    async def search_players(self, term: str, limit: int = 10) -> list[PlayerView]:
        """Búsqueda de jugadores por gamertag parcial (case-insensitive)."""
        players = await self.deps.repository.search_players(term, limit=limit)
        return [player_to_view(player) for player in players]

    async def find_player(self, xuid: str) -> PlayerView | None:
        """Proyección del jugador por XUID (o ``None`` si no está cacheado)."""
        player = await self.deps.repository.get_player(xuid)
        return player_to_view(player) if player is not None else None

    async def list_sessions(self, xuid: str, limit: int = 20) -> list[PlaySessionView]:
        """Historial de sesiones de un jugador, más recientes primero."""
        sessions = await self.deps.repository.list_sessions(xuid, limit=limit)
        return [session_to_view(session) for session in sessions]

    async def online_players(self, server_id: str) -> list[PlaySessionView]:
        """Jugadores con sesión abierta (presencia en vivo) en un servidor."""
        sessions = await self.deps.repository.list_open_sessions(server_id)
        return [session_to_view(session) for session in sessions]

    async def list_global_bans(self) -> list[GlobalBanView]:
        """Todos los bans globales, más recientes primero."""
        bans = await self.deps.ban_repository.list_global_bans()
        return [global_ban_to_view(ban) for ban in bans]

    async def list_server_bans(self, server_id: str) -> list[ServerBanView]:
        """Bans de un servidor, más recientes primero."""
        bans = await self.deps.ban_repository.list_server_bans(server_id)
        return [server_ban_to_view(ban) for ban in bans]

    async def ban_globally(self, cmd: BanPlayerGloballyCommand) -> GlobalBanView:
        return await self._ban_global.ban(cmd)

    async def unban_globally(self, cmd: UnbanPlayerGloballyCommand) -> None:
        await self._unban_global.unban(cmd)

    async def ban_on_server(self, cmd: BanPlayerOnServerCommand) -> ServerBanView:
        return await self._ban_server.ban(cmd)

    async def unban_on_server(self, cmd: UnbanPlayerOnServerCommand) -> None:
        await self._unban_server.unban(cmd)

    async def kick(self, cmd: KickPlayerCommand) -> CommandAck:
        return await self._kick.kick(cmd)

    def register_handlers(self) -> None:
        """Suscriptores del módulo sobre el bus (Blueprint §3.5)."""
        bus: EventBusPort = self.deps.bus
        bus.subscribe(PLAYER_JOINED_TOPIC, PlayerJoinedHandler(self._join))
        self._ban_enforcement = BanEnforcementHandler(self.deps)
        bus.subscribe(PLAYER_JOINED_TOPIC, self._ban_enforcement)
        bus.subscribe(PLAYER_LEFT_TOPIC, PlayerLeftHandler(self._leave))
        bus.subscribe(SERVER_STARTED_TOPIC, ServerStartedHandler(self._clean))
        bus.subscribe(PLAYER_OPERATOR_CHANGED_TOPIC, OperatorChangedHandler())

    async def await_ban_enforcement(self) -> None:
        """Espera a que terminen los kicks de enforcement en curso (tests)."""
        handler = getattr(self, "_ban_enforcement", None)
        if handler is not None:
            await handler.wait_pending()
