"""Facade pública del módulo Player (Blueprint §3.5: resolveXuid, findPlayer).

Superficie pública: ``resolve_xuid(name)`` (gamertag → XUID cacheado),
``find_player(xuid)``, sesiones/presencia (``list_sessions``,
``online_players``) y gestión vía Console (``ban``/``unban``/``kick``).
Las operaciones de sesión/presencia se conducen por eventos (handlers) en el
lado de escritura; la facade solo expone la consulta. ban/unban/kick viven en
la capa de aplicación y se exponen aquí para el paso de API (§16).
"""

from __future__ import annotations

from app.kernel.events.bus import EventBusPort
from app.modules.console.application.results import CommandAck
from app.modules.player.application.commands import (
    BanPlayerCommand,
    KickPlayerCommand,
    UnbanPlayerCommand,
)
from app.modules.player.application.handlers import (
    SERVER_STARTED_TOPIC,
    OperatorChangedHandler,
    PlayerJoinedHandler,
    PlayerLeftHandler,
    ServerStartedHandler,
)
from app.modules.player.application.results import (
    PlayerView,
    PlaySessionView,
    player_to_view,
    session_to_view,
)
from app.modules.player.application.use_cases import (
    BanPlayerUseCase,
    CleanPresenceUseCase,
    JoinPlayerUseCase,
    KickPlayerUseCase,
    LeavePlayerUseCase,
    PlayerDeps,
    ResolvePlayerUseCase,
    UnbanPlayerUseCase,
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
        self._ban = BanPlayerUseCase(deps)
        self._unban = UnbanPlayerUseCase(deps)
        self._kick = KickPlayerUseCase(deps)

    async def resolve_xuid(self, name: str) -> str | None:
        """Devuelve el XUID cacheado para un gamertag (o ``None`` si es desconocido)."""
        player = await self.deps.repository.get_player_by_name(name)
        return player.xuid if player is not None else None

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

    async def ban(self, cmd: BanPlayerCommand) -> CommandAck:
        return await self._ban.ban(cmd)

    async def unban(self, cmd: UnbanPlayerCommand) -> CommandAck:
        return await self._unban.unban(cmd)

    async def kick(self, cmd: KickPlayerCommand) -> CommandAck:
        return await self._kick.kick(cmd)

    def register_handlers(self) -> None:
        """Suscriptores del módulo sobre el bus (Blueprint §3.5)."""
        bus: EventBusPort = self.deps.bus
        bus.subscribe(PLAYER_JOINED_TOPIC, PlayerJoinedHandler(self._join))
        bus.subscribe(PLAYER_LEFT_TOPIC, PlayerLeftHandler(self._leave))
        bus.subscribe(SERVER_STARTED_TOPIC, ServerStartedHandler(self._clean))
        bus.subscribe(PLAYER_OPERATOR_CHANGED_TOPIC, OperatorChangedHandler())
