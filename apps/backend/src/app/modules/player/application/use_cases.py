"""Use cases del módulo Player (Blueprint §3.5, §16.6).

Flujos: cachear identidad XUID (nunca el gamertag como identidad única), abrir/
cerrar ``PlaySession``, historial de playtime, limpiar presencia en
``SERVER.STARTED`` y ejecutar ban/unban/kick vía la facade Console (M5: el ban
en-juego se ejecuta por comando de consola, el estado del ban vive en BDS).
``PLAYER.BANNED`` se publica solo cuando el comando se acepta por Console.

El módulo **no publica** ``PLAYER.JOINED``/``PLAYER.LEFT``: esos eventos los
publican los parsers declarativos de Console; Player solo los consume.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.kernel.events.bus import EventBusPort
from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.settings import SettingsPort
from app.kernel.time import TimeProviderPort
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.results import CommandAck
from app.modules.player.application.commands import (
    BanPlayerCommand,
    KickPlayerCommand,
    UnbanPlayerCommand,
)
from app.modules.player.application.results import (
    PlayerView,
    PlaySessionView,
    player_to_view,
    session_to_view,
)
from app.modules.player.domain.errors import PlayerNotFoundError, PlayerValidationError
from app.modules.player.domain.events import player_banned
from app.modules.player.domain.player import Player
from app.modules.player.domain.repository import PlayerRepositoryPort
from app.modules.player.domain.session import PlaySession, SessionEndReason


@dataclass(slots=True)
class PlayerDeps:
    """Dependencias comunes de los use cases del módulo Player."""

    repository: PlayerRepositoryPort
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
    """Helpers compartidos por ban/unban/kick (identidad canónica + Console)."""

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

    async def _send(self, server_id: str, command: str, actor_id: str | None) -> CommandAck:
        return await self._deps.console.send_command(
            SendCommand(server_id=server_id, command=command, actor_id=actor_id)
        )


class BanPlayerUseCase(_BanCommandMixin):
    """Ban a un jugador conocido: comando ``ban <name>`` + ``PLAYER.BANNED``."""

    async def ban(self, cmd: BanPlayerCommand) -> CommandAck:
        player = await self._require_player(cmd.xuid)
        command = f"ban {player.name}"
        ack = await self._send(cmd.server_id, command, cmd.actor_id)
        await self._deps.bus.publish(
            player_banned(
                cmd.server_id,
                player.xuid,
                player.name,
                command,
                actor_id=cmd.actor_id,
            )
        )
        return ack


class UnbanPlayerUseCase(_BanCommandMixin):
    """Desbaneo: comando ``unban <xuid>`` (sin evento de dominio)."""

    async def unban(self, cmd: UnbanPlayerCommand) -> CommandAck:
        player = await self._require_player(cmd.xuid)
        return await self._send(cmd.server_id, f"unban {player.xuid}", cmd.actor_id)


class KickPlayerUseCase(_BanCommandMixin):
    """Expulsión: comando ``kick <name>`` (sin evento de dominio)."""

    async def kick(self, cmd: KickPlayerCommand) -> CommandAck:
        player = await self._require_player(cmd.xuid)
        return await self._send(cmd.server_id, f"kick {player.name}", cmd.actor_id)


def _require_identity(xuid: str, name: str) -> None:
    if not xuid or not name:
        raise PlayerValidationError(
            "xuid y name requeridos",
            context={"xuid": xuid, "name": name},
        )
