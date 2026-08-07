"""Parser declarativo: líneas de join/leave del log → ``PLAYER.JOINED/LEFT`` (§7.3).

Consumidor externo de ``CONSOLE.OUTPUT``: reconoce el patrón de línea con el
que BDS reporta conectado/desconectado (y timeout) de un jugador y publica
``PLAYER.JOINED``/``PLAYER.LEFT`` con nombre + XUID, sin interpretar semántica
de negocio (Player resuelve el significado). Solo reconoce líneas **con XUID**
(el gamertag jamás es identidad única, §16.6). Vive fuera del núcleo de
Console, en ``infrastructure/parsers``, como marca el Blueprint. **El módulo
Player no publica estos eventos**; los parsers de Console lo hacen.
"""

from __future__ import annotations

import re

from app.kernel.events.bus import EventBusPort
from app.kernel.events.event import DomainEvent
from app.modules.player.domain.events import player_joined, player_left

_JOIN = re.compile(r"Player connected: (?P<name>.+?), xuid: (?P<xuid>\d+)", re.IGNORECASE)
_LEFT = re.compile(r"Player disconnected: (?P<name>.+?), xuid: (?P<xuid>\d+)", re.IGNORECASE)
_TIMED_OUT = re.compile(r"Player timed out: (?P<name>.+?), xuid: (?P<xuid>\d+)", re.IGNORECASE)


class PlayerJoinDetector:
    """Parser declarativo: líneas join/leave/timed-out → ``PLAYER.JOINED/LEFT``."""

    def __init__(self, bus: EventBusPort) -> None:
        self._bus = bus

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id
        if not server_id:
            return
        line = str(event.payload.get("line", ""))
        match = _JOIN.search(line)
        if match is not None:
            await self._bus.publish(
                player_joined(server_id, match.group("name"), match.group("xuid"))
            )
            return
        match = _LEFT.search(line) or _TIMED_OUT.search(line)
        if match is not None:
            await self._bus.publish(
                player_left(server_id, match.group("name"), match.group("xuid"))
            )
