"""Handlers de eventos consumidos por el módulo Player (Blueprint §3.5).

``PLAYER.JOINED``/``PLAYER.LEFT`` los publican los parsers declarativos de
Console (§7.3); Player abre/cierra sesiones. ``SERVER.STARTED`` limpia la
presencia (tras reinicio no hay nadie conectado de verdad). ``PLAYER.
OPERATOR_CHANGED`` (Permission, Fase F) se consume solo por consistencia, sin
lógica de negocio nueva. Los handlers son defensivos: payload inválido o sin
``server_id`` → no hacen nada (nunca cortan el bus).
"""

from __future__ import annotations

from app.kernel.events.event import DomainEvent
from app.modules.player.application.use_cases import (
    CleanPresenceUseCase,
    JoinPlayerUseCase,
    LeavePlayerUseCase,
)

SERVER_STARTED_TOPIC = "server.started"


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


def _extract_identity(event: DomainEvent) -> tuple[str, str] | None:
    name = event.payload.get("name")
    xuid = event.payload.get("xuid")
    if not isinstance(name, str) or not isinstance(xuid, str):
        return None
    if not name.strip() or not xuid.strip():
        return None
    return xuid, name
