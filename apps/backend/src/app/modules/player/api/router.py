"""Routers HTTP del módulo Player (vertical slice §16 ``modules/player/api``).

REST de solo consulta (resolve/find/sesiones/presencia) + gestión vía Console
(ban/unban/kick, decisión del paso de cierre). Todos los endpoints son
scoped a un servidor para reusar ``require_server_action`` (ACL por
servidor): las consultas son lectura (viewer+), la gestión es escritura
(operator+). La API solo traduce request → comando y resultado → respuesta
(Blueprint §4.7); el ban/unban/kick delega en la facade, que ejecuta el
comando en BDS vía Console.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.bootstrap.errors import http_error
from app.bootstrap.security import get_container, require_server_action
from app.kernel.errors import HttpError
from app.kernel.ports.access import Identity
from app.modules.console.application.results import CommandAck
from app.modules.player.api.schemas import (
    CommandAckResponse,
    PlayerResponse,
    PlaySessionResponse,
    ResolvePlayerResponse,
)
from app.modules.player.application.commands import (
    BanPlayerCommand,
    KickPlayerCommand,
    UnbanPlayerCommand,
)
from app.modules.player.application.facade import PlayerFacade
from app.modules.player.application.results import PlaySessionView

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


def _not_found(server_id: str, subject: str) -> HttpError:
    return http_error(
        404,
        "PLAYER.NOT_FOUND",
        "El jugador no está en la caché del panel",
        {"server_id": server_id, "subject": subject},
    )


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


@router.post(
    "/servers/{server_id}/players/{xuid}/ban",
    response_model=CommandAckResponse,
    status_code=202,
    summary="Banear a un jugador",
)
async def ban_player(
    server_id: str,
    xuid: str,
    request: Request,
    identity: Identity = Depends(require_server_action("player.manage")),
) -> CommandAckResponse:
    ack = await _facade(request).ban(
        BanPlayerCommand(server_id=server_id, xuid=xuid, actor_id=identity.id)
    )
    return _ack_response(ack)


@router.post(
    "/servers/{server_id}/players/{xuid}/unban",
    response_model=CommandAckResponse,
    status_code=202,
    summary="Desbanear a un jugador",
)
async def unban_player(
    server_id: str,
    xuid: str,
    request: Request,
    identity: Identity = Depends(require_server_action("player.manage")),
) -> CommandAckResponse:
    ack = await _facade(request).unban(
        UnbanPlayerCommand(server_id=server_id, xuid=xuid, actor_id=identity.id)
    )
    return _ack_response(ack)


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
