"""Use cases del módulo Player (Blueprint §3.5, §16.6).

Flujos: cachear identidad XUID (nunca el gamertag como identidad única), abrir/
cerrar ``PlaySession``, historial de playtime, limpiar presencia en
``SERVER.STARTED`` y ejecutar kick vía la facade Console. Los bans persistentes
(globales y por servidor, ADR-011) se aplican como estado en el panel + evento
``PLAYER.BANNED``/``PLAYER.UNBANNED``; el enforcement del kick ocurre en
``PLAYER.JOINED`` (``BanEnforcementHandler``) y, si el jugador está online al
banear por servidor, en el propio use case.

El módulo **no publica** ``PLAYER.JOINED``/``PLAYER.LEFT``: esos eventos los
publican los parsers declarativos de Console; Player solo los consume.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace

from app.kernel.events.bus import EventBusPort
from app.kernel.ids import IdGeneratorPort
from app.kernel.logging import get_logger
from app.kernel.ports.settings import SettingsPort
from app.kernel.time import TimeProviderPort
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.results import CommandAck
from app.modules.player.application.commands import (
    BanPlayerGloballyCommand,
    BanPlayerOnServerCommand,
    KickPlayerCommand,
    UnbanPlayerGloballyCommand,
    UnbanPlayerOnServerCommand,
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
from app.modules.player.domain.bans import GlobalBan, ServerBan, kick_command
from app.modules.player.domain.errors import (
    PlayerBanNotFoundError,
    PlayerNotFoundError,
    PlayerValidationError,
)
from app.modules.player.domain.events import player_banned, player_unbanned
from app.modules.player.domain.player import Player
from app.modules.player.domain.repository import (
    PlayerBanRepositoryPort,
    PlayerRepositoryPort,
)
from app.modules.player.domain.session import PlaySession, SessionEndReason

logger = get_logger(__name__)


@dataclass(slots=True)
class PlayerDeps:
    """Dependencias comunes de los use cases del módulo Player."""

    repository: PlayerRepositoryPort
    ban_repository: PlayerBanRepositoryPort
    console: ConsoleFacade
    bus: EventBusPort
    ids: IdGeneratorPort
    time: TimeProviderPort
    settings: SettingsPort


class ResolvePlayerUseCase:
    """Caché de identidad: asegura un ``Player`` por XUID y refresca su nombre."""

    def __init__(self, deps: PlayerDeps) -> None:
        self._deps = deps

    async def cache(self, xuid: str, name: str) -> PlayerView:
        """Upsert del jugador (crea si no existe, refresca nombre/última visita)."""
        xuid = xuid.strip()
        name = name.strip()
        _require_identity(xuid, name)
        now = self._deps.time.now()
        player = await self._deps.repository.get_player(xuid)
        if player is None:
            player = Player(
                xuid=xuid,
                name=name,
                first_seen_at=now,
                last_seen_at=now,
                playtime_seconds=0,
                created_at=now,
                updated_at=now,
            )
        else:
            player = replace(
                player,
                name=name,
                last_seen_at=now,
                updated_at=now,
            )
        await self._deps.repository.save_player(player)
        return player_to_view(player)


class JoinPlayerUseCase:
    """``PLAYER.JOINED`` → presencia: abre una sesión (idempotente)."""

    def __init__(self, deps: PlayerDeps) -> None:
        self._deps = deps
        self._resolve = ResolvePlayerUseCase(deps)

    async def join(self, server_id: str, xuid: str, name: str) -> PlaySessionView:
        """Registra la identidad y abre la sesión; si ya está abierta, no duplica."""
        server_id = server_id.strip()
        _require_identity(xuid, name)
        if not server_id:
            raise PlayerValidationError("server_id requerido", context={"server_id": server_id})
        await self._resolve.cache(xuid, name)
        existing = await self._deps.repository.get_open_session(server_id, xuid)
        if existing is not None:
            return session_to_view(existing)
        session = PlaySession(
            id=self._deps.ids.new_id(),
            server_id=server_id,
            xuid=xuid,
            joined_at=self._deps.time.now(),
        )
        await self._deps.repository.save_session(session)
        return session_to_view(session)


class LeavePlayerUseCase:
    """``PLAYER.LEFT`` → cierra la sesión y acumula el playtime.

    Si no hay sesión abierta (hueco de presencia tras reinicio/línea perdida)
    no lanza: solo refresca la caché y devuelve ``None`` (defensivo, §16.6).
    """

    def __init__(self, deps: PlayerDeps) -> None:
        self._deps = deps
        self._resolve = ResolvePlayerUseCase(deps)

    async def leave(
        self,
        server_id: str,
        xuid: str,
        name: str,
    ) -> PlaySessionView | None:
        server_id = server_id.strip()
        _require_identity(xuid, name)
        if not server_id:
            raise PlayerValidationError("server_id requerido", context={"server_id": server_id})
        await self._resolve.cache(xuid, name)
        session = await self._deps.repository.get_open_session(server_id, xuid)
        if session is None:
            return None
        now = self._deps.time.now()
        closed = replace(
            session,
            left_at=now,
            reason=SessionEndReason.LEFT,
            playtime_seconds=session.elapsed_seconds(now),
        )
        await self._deps.repository.save_session(closed)
        await self._accumulate_playtime(xuid, closed.playtime_seconds)
        return session_to_view(closed)

    async def _accumulate_playtime(self, xuid: str, seconds: int) -> None:
        player = await self._deps.repository.get_player(xuid)
        if player is None:
            return
        updated = replace(
            player,
            playtime_seconds=player.playtime_seconds + seconds,
            updated_at=self._deps.time.now(),
        )
        await self._deps.repository.save_player(updated)


class CleanPresenceUseCase:
    """``SERVER.STARTED`` → limpia la presencia tras un reinicio.

    Al arrancar de nuevo, ningún jugador está realmente conectado aunque el
    estado previo dijera lo contrario: cierra las sesiones abiertas como
    ``ABORTED`` **sin acumular playtime** (no se conoce el fin real).
    """

    def __init__(self, deps: PlayerDeps) -> None:
        self._deps = deps

    async def clean(self, server_id: str) -> int:
        """Cierra las sesiones abiertas del servidor; devuelve cuántas cerró."""
        server_id = server_id.strip()
        if not server_id:
            raise PlayerValidationError("server_id requerido", context={"server_id": server_id})
        now = self._deps.time.now()
        count = 0
        for session in await self._deps.repository.list_open_sessions(server_id):
            aborted = replace(
                session,
                left_at=now,
                reason=SessionEndReason.ABORTED,
                playtime_seconds=0,
            )
            await self._deps.repository.save_session(aborted)
            count += 1
        return count


class _BanCommandMixin:
    """Helpers compartidos por el kick (identidad canónica + Console)."""

    def __init__(self, deps: PlayerDeps) -> None:
        self._deps = deps

    async def _require_player(self, xuid: str) -> Player:
        xuid = xuid.strip()
        if not xuid:
            raise PlayerValidationError("xuid requerido", context={"xuid": xuid})
        player = await self._deps.repository.get_player(xuid)
        if player is None:
            raise PlayerNotFoundError(
                "Jugador desconocido para el panel",
                context={"xuid": xuid},
            )
        return player


# -- kick con reintento (race "Player connected" → "Player Spawned") -----------

KICK_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 2.0)
KICK_OBSERVE_WINDOW_SECONDS = 0.6
KICK_MAX_ATTEMPTS = 3
SERVER_BAN_KICK_DEFAULT_REASON = "Baneado del servidor"
KICK_ERROR_MARKERS: tuple[str, ...] = (
    "no targets matched selector",
    "could not find player",
)


async def kick_with_retry(
    deps: PlayerDeps,
    server_id: str,
    xuid: str,
    gamertag: str,
    reason: str | None,
    actor_id: str | None,
) -> CommandAck:
    """``kick <gamertag>`` con reintento acotado y cortado si el jugador se fue.

    BDS tarda ~5s entre ``Player connected`` y ``Player Spawned``; en esa
    ventana el jugador no es un target válido y el kick falla con
    "No targets matched selector". Se observa la salida posterior a cada envío
    (``send_command_and_observe``) y se reintenta con backoff corto si aparece
    el patrón de error, hasta agotar ``KICK_MAX_ATTEMPTS`` intentos.

    **Antes de cada reintento** se verifica que el jugador siga conectado
    (sesión abierta en ``player_sessions`` con ``left_at IS NULL`` para ese
    servidor): si ya se desconectó, se corta el retry — no tiene sentido seguir
    expulsando a quien no está. El fallo final se loguea estructurado
    (``player.ban_kick_failed``) en vez de ser silencioso.
    """
    command = kick_command(gamertag, reason)
    max_attempts = KICK_MAX_ATTEMPTS
    last_ack: CommandAck | None = None
    for attempt in range(1, max_attempts + 1):
        if attempt > 1 and not await _is_online(deps, server_id, xuid):
            logger.info(
                "player.ban_kick_aborted",
                extra={
                    "server_id": server_id,
                    "gamertag": gamertag,
                    "attempt": attempt,
                    "command": command,
                },
            )
            assert last_ack is not None
            return last_ack
        observation = await deps.console.send_command_and_observe(
            SendCommand(server_id=server_id, command=command, actor_id=actor_id),
            window_s=KICK_OBSERVE_WINDOW_SECONDS,
        )
        last_ack = observation.ack
        if not _kick_output_failed(observation.lines):
            logger.info(
                "player.ban_kick_confirmed",
                extra={
                    "server_id": server_id,
                    "gamertag": gamertag,
                    "attempt": attempt,
                    "command": command,
                },
            )
            return last_ack
        if attempt < max_attempts:
            await asyncio.sleep(KICK_RETRY_BACKOFF_SECONDS[attempt - 1])
    logger.warning(
        "player.ban_kick_failed",
        extra={
            "server_id": server_id,
            "gamertag": gamertag,
            "reason": reason,
            "attempts": max_attempts,
            "command": command,
        },
    )
    assert last_ack is not None
    return last_ack


def _kick_output_failed(lines: tuple[str, ...]) -> bool:
    """¿La salida observada contiene un error de target de BDS?"""
    text = "\n".join(lines).lower()
    return any(marker in text for marker in KICK_ERROR_MARKERS)


class KickPlayerUseCase(_BanCommandMixin):
    """Expulsión: comando ``kick <name>`` (sin evento de dominio).

    Reintenta con backoff si BDS responde "No targets matched selector" (el
    jugador aún no ha spawnado, race de ~5s entre ``Player connected`` y
    ``Player Spawned``). Devuelve el acuse del último envío.
    """

    async def kick(self, cmd: KickPlayerCommand) -> CommandAck:
        player = await self._require_player(cmd.xuid)
        return await kick_with_retry(
            self._deps,
            cmd.server_id,
            player.xuid,
            player.name,
            None,
            cmd.actor_id,
        )


# -- bans persistentes (ADR-011) ---------------------------------------------


class BanPlayerGloballyUseCase:
    """Crea/actualiza un ban global y publica ``PLAYER.BANNED`` (scope global)."""

    def __init__(self, deps: PlayerDeps) -> None:
        self._deps = deps

    async def ban(self, cmd: BanPlayerGloballyCommand) -> GlobalBanView:
        deps = self._deps
        gamertag = cmd.gamertag.strip()
        if not gamertag:
            raise PlayerValidationError("gamertag requerido", context={"gamertag": cmd.gamertag})
        xuid = cmd.xuid.strip() if cmd.xuid else None
        now = deps.time.now()
        existing = await deps.ban_repository.get_global_ban_by_gamertag(gamertag)
        ban = GlobalBan(
            id=existing.id if existing is not None else deps.ids.new_id(),
            xuid=xuid,
            gamertag=gamertag,
            reason=cmd.reason,
            banned_by=cmd.actor_id or "",
            created_at=existing.created_at if existing is not None else now,
            expires_at=cmd.expires_at,
        )
        await deps.ban_repository.save_global_ban(ban)
        # Kick inmediato si está conectado ahora mismo (no esperar PLAYER.JOINED).
        # Un ban global aplica en cualquier servidor: se expulsa de cada sesión
        # abierta del jugador. Si no se conoce el ``xuid`` no se puede localizar
        # la sesión, así que el enforcement por join cubrirá futuras entradas.
        if xuid:
            await _kick_global_sessions(deps, ban, cmd.actor_id)
        await deps.bus.publish(
            player_banned(
                "global",
                ban.xuid,
                ban.gamertag,
                ban.reason,
                actor_id=cmd.actor_id,
            )
        )
        return global_ban_to_view(ban)


class UnbanPlayerGloballyUseCase:
    """Quita un ban global y publica ``PLAYER.UNBANNED`` (scope global)."""

    def __init__(self, deps: PlayerDeps) -> None:
        self._deps = deps

    async def unban(self, cmd: UnbanPlayerGloballyCommand) -> None:
        deps = self._deps
        ban = await deps.ban_repository.get_global_ban(cmd.ban_id)
        if ban is None:
            raise PlayerBanNotFoundError(
                "Ban global no encontrado",
                context={"ban_id": cmd.ban_id},
            )
        await deps.ban_repository.delete_global_ban(cmd.ban_id)
        await deps.bus.publish(
            player_unbanned(
                "global",
                ban.xuid,
                ban.gamertag,
                ban.reason,
                ban_id=ban.id,
                actor_id=cmd.actor_id,
            )
        )


class BanPlayerOnServerUseCase:
    """Crea/actualiza un ban por servidor y expulsa al jugador si está online."""

    def __init__(self, deps: PlayerDeps) -> None:
        self._deps = deps

    async def ban(self, cmd: BanPlayerOnServerCommand) -> ServerBanView:
        deps = self._deps
        xuid = cmd.player_id.strip()
        if not xuid:
            raise PlayerValidationError("player_id requerido", context={"player_id": cmd.player_id})
        if not cmd.server_id:
            raise PlayerValidationError(
                "server_id requerido",
                context={"server_id": cmd.server_id},
            )
        player = await deps.repository.get_player(xuid)
        if player is None:
            raise PlayerNotFoundError(
                "Jugador desconocido para el panel",
                context={"xuid": xuid},
            )
        gamertag = player.name
        now = deps.time.now()
        existing = await deps.ban_repository.get_server_ban_by_gamertag(cmd.server_id, gamertag)
        ban = ServerBan(
            id=existing.id if existing is not None else deps.ids.new_id(),
            server_id=cmd.server_id,
            xuid=xuid,
            gamertag=gamertag,
            reason=cmd.reason,
            banned_by=cmd.actor_id or "",
            created_at=existing.created_at if existing is not None else now,
            expires_at=cmd.expires_at,
        )
        await deps.ban_repository.save_server_ban(ban)
        if await _is_online(deps, cmd.server_id, xuid):
            await _kick_best_effort(
                deps,
                cmd.server_id,
                xuid,
                gamertag,
                cmd.reason or SERVER_BAN_KICK_DEFAULT_REASON,
                cmd.actor_id,
            )
        await deps.bus.publish(
            player_banned(
                "server",
                ban.xuid,
                ban.gamertag,
                ban.reason,
                server_id=cmd.server_id,
                actor_id=cmd.actor_id,
            )
        )
        return server_ban_to_view(ban)


class UnbanPlayerOnServerUseCase:
    """Quita el ban por servidor de un jugador y publica ``PLAYER.UNBANNED``."""

    def __init__(self, deps: PlayerDeps) -> None:
        self._deps = deps

    async def unban(self, cmd: UnbanPlayerOnServerCommand) -> None:
        deps = self._deps
        xuid = cmd.player_id.strip()
        if not xuid:
            raise PlayerValidationError("player_id requerido", context={"player_id": cmd.player_id})
        if not cmd.server_id:
            raise PlayerValidationError(
                "server_id requerido",
                context={"server_id": cmd.server_id},
            )
        player = await deps.repository.get_player(xuid)
        if player is None:
            raise PlayerNotFoundError(
                "Jugador desconocido para el panel",
                context={"xuid": xuid},
            )
        ban = await deps.ban_repository.get_server_ban_by_gamertag(cmd.server_id, player.name)
        if ban is None:
            raise PlayerBanNotFoundError(
                "Ban por servidor no encontrado",
                context={"server_id": cmd.server_id, "player_id": xuid},
            )
        await deps.ban_repository.delete_server_ban(cmd.server_id, ban.id)
        await deps.bus.publish(
            player_unbanned(
                "server",
                ban.xuid,
                ban.gamertag,
                ban.reason,
                server_id=cmd.server_id,
                ban_id=ban.id,
                actor_id=cmd.actor_id,
            )
        )


async def _is_online(deps: PlayerDeps, server_id: str, xuid: str) -> bool:
    """Presencia en vivo: hay una ``PlaySession`` abierta del jugador en el server."""
    session = await deps.repository.get_open_session(server_id, xuid)
    return session is not None


async def _kick_best_effort(
    deps: PlayerDeps,
    server_id: str,
    xuid: str,
    gamertag: str,
    reason: str | None,
    actor_id: str | None,
) -> None:
    """Expulsa al jugador; si el server no corre (presencia obsoleta) solo loguea.

    El ban ya quedó persistido: un fallo de kick (p. ej. servidor parado con
    sesión abierta residual) no debe romper el request (ADR-011, defensivo). El
    kick reintenta con backoff si BDS aún no tiene al jugador spawnado
    (``kick_with_retry``) y loguea el fallo final estructurado.
    """
    try:
        await kick_with_retry(deps, server_id, xuid, gamertag, reason, actor_id)
    except Exception:  # noqa: BLE001 — best-effort, el ban ya está persistido
        logger.warning(
            "player.ban_kick_failed",
            extra={"server_id": server_id, "gamertag": gamertag, "reason": reason},
        )


async def _kick_global_sessions(
    deps: PlayerDeps,
    ban: GlobalBan,
    actor_id: str | None,
) -> None:
    """Expulsa al jugador de cada servidor donde esté conectado ahora mismo.

    Aplica un ban global en vivo: no espera a ``PLAYER.JOINED`` (ese evento no
    se dispara para quien ya está conectado). Es best-effort por iteración: el
    ban ya está persistido, un fallo en una sesión no rompe el request ni
    impide expulsar del resto.
    """
    assert ban.xuid is not None
    sessions = await deps.repository.list_open_sessions_by_xuid(ban.xuid)
    for session in sessions:
        await _kick_best_effort(
            deps,
            session.server_id,
            ban.xuid,
            ban.gamertag,
            ban.reason,
            actor_id,
        )


def _require_identity(xuid: str, name: str) -> None:
    if not xuid or not name:
        raise PlayerValidationError(
            "xuid y name requeridos",
            context={"xuid": xuid, "name": name},
        )
