"""Handlers de eventos consumidos por el módulo Player (Blueprint §3.5).

``PLAYER.JOINED``/``PLAYER.LEFT`` los publican los parsers declarativos de
Console (§7.3); Player abre/cierra sesiones y aplica el enforcement de bans en
``PLAYER.JOINED`` (``BanEnforcementHandler``). ``SERVER.STARTED`` limpia la
presencia (tras reinicio no hay nadie conectado de verdad). ``PLAYER.
OPERATOR_CHANGED`` (Permission, Fase F) se consume solo por consistencia, sin
lógica de negocio nueva. Los handlers son defensivos: payload inválido o sin
``server_id`` → no hacen nada (nunca cortan el bus).
"""

from __future__ import annotations

import asyncio

from app.kernel.events.event import DomainEvent
from app.kernel.logging import get_logger
from app.modules.player.application.use_cases import (
    CleanPresenceUseCase,
    JoinPlayerUseCase,
    LeavePlayerUseCase,
    PlayerDeps,
    _is_online,
    kick_with_retry,
)
from app.modules.player.domain.bans import (
    BanScope,
    GlobalBan,
    ServerBan,
    is_valid_xuid,
)

SERVER_STARTED_TOPIC = "server.started"

logger = get_logger(__name__)


class PlayerJoinedHandler:
    """``PLAYER.JOINED`` → abre la sesión del jugador."""

    def __init__(self, join: JoinPlayerUseCase) -> None:
        self._join = join

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id or event.payload.get("server_id")
        if not server_id:
            return
        identity = _extract_identity(event)
        if identity is None:
            return
        await self._join.join(str(server_id), identity[0], identity[1])


class PlayerLeftHandler:
    """``PLAYER.LEFT`` → cierra la sesión y acumula playtime."""

    def __init__(self, leave: LeavePlayerUseCase) -> None:
        self._leave = leave

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id or event.payload.get("server_id")
        if not server_id:
            return
        identity = _extract_identity(event)
        if identity is None:
            return
        await self._leave.leave(str(server_id), identity[0], identity[1])


class ServerStartedHandler:
    """``SERVER.STARTED`` → limpia la presencia del servidor (sesiones abiertas)."""

    def __init__(self, clean: CleanPresenceUseCase) -> None:
        self._clean = clean

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id or event.payload.get("server_id")
        if not server_id:
            return
        await self._clean.clean(str(server_id))


class OperatorChangedHandler:
    """``PLAYER.OPERATOR_CHANGED`` — consistencia únicamente (Blueprint §3.5).

    Permission publica este evento; Player lo consume sin lógica de negocio
    nueva. Defensivo: valida el payload y no hace nada más.
    """

    async def __call__(self, event: DomainEvent) -> None:
        xuid = event.payload.get("xuid")
        if not xuid or not isinstance(xuid, str):
            return


class BanEnforcementHandler:
    """``PLAYER.JOINED`` → expulsa si hay un ban activo (global o por servidor).

    Chequea primero ``player_global_bans`` y luego el ban por servidor, con
    fallback ``xuid`` → ``gamertag`` (case-insensitive) cuando el XUID es
    ``0``/ausente (ADR-011: "ban blando" de disuasión en offline, no seguridad
    real). Respeta ``expires_at`` (ban vencido = no aplica). Defensivo: nunca
    corta el bus; el kick aplicado se loguea estructurado.

    El kick se ejecuta en un **task de fondo**: el handler corre inline dentro
    de la cadena de ``bus.publish`` de ``ConsoleLogStream.consume`` (el ``PLAYER
    .JOINED`` lo publica ``PlayerJoinDetector``, que es un handler de
    ``CONSOLE.OUTPUT``). Si el kick esperara inline la ventana de observación,
    bloquearía al consumidor del stream, que es precisamente quien entrega la
    respuesta de BDS al comando (self-deadlock, bug real). En task separado el
    consumidor sigue libre y ``send_command_and_observe`` puede ver el error.
    """

    def __init__(self, deps: PlayerDeps) -> None:
        self._deps = deps
        self._tasks: set[asyncio.Task[None]] = set()

    async def __call__(self, event: DomainEvent) -> None:
        task = asyncio.create_task(self._enforce_safely(event))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _enforce_safely(self, event: DomainEvent) -> None:
        try:
            await self._enforce(event)
        except Exception:  # noqa: BLE001 — defensivo, no rompe el bus
            logger.warning(
                "player.ban_enforcement_failed",
                extra={"event": event.type, "server_id": event.server_id},
            )

    async def wait_pending(self) -> None:
        """Espera a que terminen los kicks en curso (tests / shutdown)."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _enforce(self, event: DomainEvent) -> None:
        deps = self._deps
        server_id = event.server_id or event.payload.get("server_id")
        if not server_id:
            return
        xuid_raw = event.payload.get("xuid")
        gamertag_raw = event.payload.get("name")
        if not isinstance(xuid_raw, str) or not isinstance(gamertag_raw, str):
            return
        xuid = xuid_raw.strip()
        gamertag = gamertag_raw.strip()
        if not gamertag:
            return
        match = await self._find_active_ban(str(server_id), xuid, gamertag)
        if match is None:
            return
        scope, reason = match
        if not await _is_online(deps, str(server_id), xuid):
            logger.info(
                "player.ban_skip_offline",
                extra={
                    "scope": scope,
                    "server_id": server_id,
                    "gamertag": gamertag,
                    "reason": reason,
                },
            )
            return
        await kick_with_retry(deps, str(server_id), xuid, gamertag, reason, None)
        logger.info(
            "player.ban_enforced",
            extra={
                "scope": scope,
                "server_id": server_id,
                "gamertag": gamertag,
                "reason": reason,
            },
        )

    async def _find_active_ban(
        self, server_id: str, xuid: str, gamertag: str
    ) -> tuple[str, str | None] | None:
        deps = self._deps
        global_ban = await self._match_global(xuid, gamertag)
        if global_ban is not None and global_ban.is_active(deps.time.now()):
            return BanScope.GLOBAL.value, global_ban.reason
        server_ban = await self._match_server(server_id, xuid, gamertag)
        if server_ban is not None and server_ban.is_active(deps.time.now()):
            return BanScope.SERVER.value, server_ban.reason
        return None

    async def _match_global(self, xuid: str, gamertag: str) -> GlobalBan | None:
        if is_valid_xuid(xuid):
            ban = await self._deps.ban_repository.get_active_global_ban_by_xuid(xuid)
            if ban is not None:
                return ban
        return await self._deps.ban_repository.get_active_global_ban_by_gamertag(gamertag)

    async def _match_server(self, server_id: str, xuid: str, gamertag: str) -> ServerBan | None:
        if is_valid_xuid(xuid):
            ban = await self._deps.ban_repository.get_active_server_ban_by_xuid(server_id, xuid)
            if ban is not None:
                return ban
        return await self._deps.ban_repository.get_active_server_ban_by_gamertag(
            server_id, gamertag
        )


def _extract_identity(event: DomainEvent) -> tuple[str, str] | None:
    name = event.payload.get("name")
    xuid = event.payload.get("xuid")
    if not isinstance(name, str) or not isinstance(xuid, str):
        return None
    if not name.strip() or not xuid.strip():
        return None
    return xuid, name
