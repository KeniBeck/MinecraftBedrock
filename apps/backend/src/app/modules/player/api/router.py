"""Routers HTTP del módulo Player (vertical slice §16 ``modules/player/api``).

REST de solo consulta (resolve/find/sesiones/presencia), gestión de bans
persistidos (globales y por servidor, ADR-011) y expulsión vía Console
(``kick``). Los endpoints scoped a un servidor reusan ``require_server_action``
(ACL por servidor): las consultas son lectura (viewer+), la gestión es
escritura (operator+, ``permission.write``). Los bans globales son una decisión
panel-wide y exigen admin global (``require_action``). La API solo traduce
request → comando y resultado → respuesta (Blueprint §4.7); el kick delega en
la facade, que ejecuta el comando en BDS vía Console.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.bootstrap.errors import http_error
from app.bootstrap.security import (
    get_container,
    require_action,
    require_server_action,
)
from app.kernel.errors import HttpError
from app.kernel.ports.access import Identity
from app.modules.console.application.results import CommandAck
from app.modules.player.api.schemas import (
    BanPlayerRequest,
    CommandAckResponse,
    GlobalBanRequest,
    GlobalBanResponse,
    PlayerResponse,
    PlaySessionResponse,
    ResolvePlayerResponse,
)
from app.modules.player.application.commands import (
    BanPlayerGloballyCommand,
    BanPlayerOnServerCommand,
    KickPlayerCommand,
    UnbanPlayerGloballyCommand,
    UnbanPlayerOnServerCommand,
)
from app.modules.player.application.facade import PlayerFacade
from app.modules.player.application.results import GlobalBanView, PlaySessionView
from app.modules.player.domain.errors import (
    PlayerBanNotFoundError,
    PlayerNotFoundError,
)

router = APIRouter(tags=["player"])


def _facade(request: Request) -> PlayerFacade:
    return get_container(request).player_facade


def _session_response(view: PlaySessionView) -> PlaySessionResponse:
    return PlaySessionResponse(
        id=view.id,
        server_id=view.server_id,
        xuid=view.xuid,
        joined_at=view.joined_at,
        left_at=view.left_at,
        reason=view.reason,
        playtime_seconds=view.playtime_seconds,
    )


def _ack_response(ack: CommandAck) -> CommandAckResponse:
    return CommandAckResponse(
        server_id=ack.server_id,
        command=ack.command,
        priority=ack.priority.value,
        seq=ack.seq,
        at=ack.at,
    )


def _global_ban_response(view: GlobalBanView) -> GlobalBanResponse:
    return GlobalBanResponse(
        id=view.id,
        scope=view.scope,
        gamertag=view.gamertag,
        xuid=view.xuid,
        reason=view.reason,
        banned_by=view.banned_by,
        created_at=view.created_at,
        expires_at=view.expires_at,
    )


def _not_found(server_id: str, subject: str) -> HttpError:
    return http_error(
        404,
        "PLAYER.NOT_FOUND",
        "El jugador no está en la caché del panel",
        {"server_id": server_id, "subject": subject},
    )


def _handle_player_errors(exc: Exception) -> None:
    """Traduce errores de dominio a errores HTTP para los endpoints de ban."""
    if isinstance(exc, PlayerNotFoundError):
        raise http_error(
            404,
            exc.code,
            "El jugador no está en la caché del panel",
            exc.context,
        ) from exc
    if isinstance(exc, PlayerBanNotFoundError):
        raise http_error(
            404,
            exc.code,
            "El ban no existe en el panel",
            exc.context,
        ) from exc


@router.get(
    "/servers/{server_id}/players/search",
    response_model=ResolvePlayerResponse,
    summary="Resolver gamertag → XUID",
)
async def search_player(
    server_id: str,
    request: Request,
    name: str,
    identity: Identity = Depends(require_server_action("player.list")),
) -> ResolvePlayerResponse:
    del identity
    xuid = await _facade(request).resolve_xuid(name)
    if xuid is None:
        raise _not_found(server_id, name)
    return ResolvePlayerResponse(server_id=server_id, name=name, xuid=xuid)


@router.get(
    "/servers/{server_id}/players/online",
    response_model=list[PlaySessionResponse],
    summary="Jugadores con sesión abierta en el servidor",
)
async def online_players(
    server_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("player.online")),
) -> list[PlaySessionResponse]:
    del identity
    sessions = await _facade(request).online_players(server_id)
    return [_session_response(session) for session in sessions]


@router.get(
    "/servers/{server_id}/players/{xuid}",
    response_model=PlayerResponse,
    summary="Datos de un jugador por XUID",
)
async def get_player(
    server_id: str,
    xuid: str,
    request: Request,
    identity: Identity = Depends(require_server_action("player.view")),
) -> PlayerResponse:
    del identity
    view = await _facade(request).find_player(xuid)
    if view is None:
        raise _not_found(server_id, xuid)
    return PlayerResponse(
        xuid=view.xuid,
        name=view.name,
        first_seen_at=view.first_seen_at,
        last_seen_at=view.last_seen_at,
        playtime_seconds=view.playtime_seconds,
    )


@router.get(
    "/servers/{server_id}/players/{xuid}/sessions",
    response_model=list[PlaySessionResponse],
    summary="Historial de sesiones de un jugador",
)
async def player_sessions(
    server_id: str,
    xuid: str,
    request: Request,
    limit: int = 20,
    identity: Identity = Depends(require_server_action("player.sessions")),
) -> list[PlaySessionResponse]:
    del identity
    sessions = await _facade(request).list_sessions(xuid, limit=limit)
    return [_session_response(session) for session in sessions]


# -- bans globales (decisión panel-wide, admin global) ------------------------


@router.post(
    "/players/bans/global",
    response_model=GlobalBanResponse,
    status_code=201,
    summary="Ban global (panel-wide, no atado a un servidor)",
)
async def ban_player_globally(
    body: GlobalBanRequest,
    request: Request,
    identity: Identity = Depends(require_action("player.ban.global")),
) -> GlobalBanResponse:
    view = await _facade(request).ban_globally(
        BanPlayerGloballyCommand(
            gamertag=body.gamertag,
            xuid=body.xuid,
            reason=body.reason,
            expires_at=body.expires_at,
            actor_id=identity.id,
        )
    )
    return _global_ban_response(view)


@router.delete(
    "/players/bans/global/{ban_id}",
    status_code=204,
    summary="Quitar un ban global",
)
async def unban_player_globally(
    ban_id: str,
    request: Request,
    identity: Identity = Depends(require_action("player.ban.global")),
) -> None:
    try:
        await _facade(request).unban_globally(
            UnbanPlayerGloballyCommand(ban_id=ban_id, actor_id=identity.id)
        )
    except PlayerBanNotFoundError as exc:
        _handle_player_errors(exc)


# -- bans por servidor y kick (operator+, ACL por servidor) -------------------


@router.post(
    "/servers/{server_id}/players/{player_id}/ban",
    status_code=204,
    summary="Banear a un jugador (por servidor)",
)
async def ban_player_on_server(
    server_id: str,
    player_id: str,
    body: BanPlayerRequest,
    request: Request,
    identity: Identity = Depends(require_server_action("permission.write")),
) -> None:
    try:
        await _facade(request).ban_on_server(
            BanPlayerOnServerCommand(
                server_id=server_id,
                player_id=player_id,
                reason=body.reason,
                expires_at=body.expires_at,
                actor_id=identity.id,
            )
        )
    except (PlayerNotFoundError, PlayerBanNotFoundError) as exc:
        _handle_player_errors(exc)


@router.delete(
    "/servers/{server_id}/players/{player_id}/ban",
    status_code=204,
    summary="Desbanear a un jugador (por servidor)",
)
async def unban_player_on_server(
    server_id: str,
    player_id: str,
    request: Request,
    identity: Identity = Depends(require_server_action("permission.write")),
) -> None:
    try:
        await _facade(request).unban_on_server(
            UnbanPlayerOnServerCommand(
                server_id=server_id,
                player_id=player_id,
                actor_id=identity.id,
            )
        )
    except (PlayerNotFoundError, PlayerBanNotFoundError) as exc:
        _handle_player_errors(exc)


@router.post(
    "/servers/{server_id}/players/{xuid}/kick",
    response_model=CommandAckResponse,
    status_code=202,
    summary="Expulsar a un jugador",
)
async def kick_player(
    server_id: str,
    xuid: str,
    request: Request,
    identity: Identity = Depends(require_server_action("player.manage")),
) -> CommandAckResponse:
    ack = await _facade(request).kick(
        KickPlayerCommand(server_id=server_id, xuid=xuid, actor_id=identity.id)
    )
    return _ack_response(ack)
