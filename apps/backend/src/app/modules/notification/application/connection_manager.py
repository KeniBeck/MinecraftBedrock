"""Gestión de conexiones WebSocket activas (Blueprint §3.12).

Un ``ClientConnection`` agrupa el estado de una conexión: el ``Identity``
autenticado, sus canales suscritos, su buffer de salida (cola asíncrona con
tope) y la política de backpressure. El ``ConnectionManager`` mantiene el
mapeo ``channel -> {connection_id}`` y ``connection -> {channels}`` y difunde
envelopes a todas las conexiones suscritas respetando la política por tipo de
evento: los de consola usan ``drop-oldest`` (descartar el más antiguo del
buffer) y los críticos se marcan para cierre de conexión si el buffer está
lleno (rechazo).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from app.kernel.ports.access import Identity

logger = logging.getLogger(__name__)

# Tipos críticos: si el buffer está lleno, se rechaza (cierra la conexión).
_CRITICAL_PREFIXES = ("SERVER.", "BACKUP.", "WORLD.", "TASK.")
_MAX_BUFFER = 1000


def _is_critical(event_type: str) -> bool:
    return any(event_type.startswith(prefix) for prefix in _CRITICAL_PREFIXES)


@dataclass
class ClientConnection:
    """Estado mutable de una conexión WebSocket activa."""

    connection_id: str
    identity: Identity
    max_buffer: int = _MAX_BUFFER
    channels: set[str] = field(default_factory=set)
    close_requested: bool = False
    buffer: asyncio.Queue[dict[str, Any]] = field(init=False)
    rate_limiter: Any = None

    def __post_init__(self) -> None:
        self.buffer = asyncio.Queue(maxsize=self.max_buffer)

    @property
    def pending(self) -> int:
        return self.buffer.qsize()

    def enqueue(self, envelope: dict[str, Any]) -> bool:
        """Encola un mensaje aplicando la política de backpressure.

        Devuelve ``True`` si se aceptó. Con buffer lleno: para eventos de
        consola se descarta el más antiguo (drop-oldest) y se encola el nuevo;
        para críticos se marca ``close_requested`` (rechazo, cierra al volcar
        el buffer).
        """
        event = str(envelope.get("event", ""))
        try:
            self.buffer.put_nowait(envelope)
            return True
        except asyncio.QueueFull:
            pass

        if _is_critical(event):
            self.close_requested = True
            return False

        self._drop_oldest()
        with suppress(asyncio.QueueFull):
            self.buffer.put_nowait(envelope)
        return True

    def _drop_oldest(self) -> None:
        with suppress(asyncio.QueueEmpty):
            self.buffer.get_nowait()


class ConnectionManager:
    """Registra conexiones y difunde envelopes por canal."""

    def __init__(self) -> None:
        self._connections: dict[str, ClientConnection] = {}
        self._by_channel: dict[str, set[str]] = {}

    @property
    def connections(self) -> dict[str, ClientConnection]:
        return self._connections

    @property
    def count(self) -> int:
        return len(self._connections)

    def register(self, connection: ClientConnection) -> None:
        self._connections[connection.connection_id] = connection

    def unregister(self, connection_id: str) -> None:
        connection = self._connections.pop(connection_id, None)
        if connection is None:
            return
        for channel in connection.channels:
            subscribers = self._by_channel.get(channel)
            if subscribers is None:
                continue
            subscribers.discard(connection_id)
            if not subscribers:
                self._by_channel.pop(channel, None)

    def get(self, connection_id: str) -> ClientConnection | None:
        return self._connections.get(connection_id)

    def _add_to_channel(self, connection: ClientConnection, channel: str) -> None:
        self._by_channel.setdefault(channel, set()).add(connection.connection_id)
        connection.channels.add(channel)

    def subscribe(self, connection_id: str, channel: str) -> None:
        connection = self._connections.get(connection_id)
        if connection is None:
            raise KeyError(connection_id)
        self._add_to_channel(connection, channel)

    def unsubscribe(self, connection_id: str, channel: str) -> None:
        connection = self._connections.get(connection_id)
        if connection is None:
            return
        connection.channels.discard(channel)
        subscribers = self._by_channel.get(channel)
        if subscribers is None:
            return
        subscribers.discard(connection_id)
        if not subscribers:
            self._by_channel.pop(channel, None)

    def subscribed_channels(self, connection_id: str) -> set[str]:
        connection = self._connections.get(connection_id)
        return set(connection.channels) if connection is not None else set()

    def broadcast_to_channel(self, channel: str, envelope: dict[str, Any]) -> int:
        """Encoda el envelope a todas las conexiones del canal.

        Devuelve el número de conexiones que aceptaron el mensaje (o, para
        críticos con buffer lleno, que quedaron marcadas para cierre).
        """
        subscribers = self._by_channel.get(channel)
        if not subscribers:
            return 0
        delivered = 0
        for connection_id in list(subscribers):
            connection = self._connections.get(connection_id)
            if connection is None:
                continue
            if connection.enqueue(envelope):
                delivered += 1
        return delivered

    def broadcast_to_channels(self, channels: set[str], envelope: dict[str, Any]) -> int:
        """Difunde a varias canales; devuelve total de conexiones atendidas."""
        total = 0
        for channel in channels:
            subscribers = self._by_channel.get(channel)
            if subscribers:
                total += self.broadcast_to_channel(channel, envelope)
        return total

    def connection_ids_for(self, channel: str) -> set[str]:
        return set(self._by_channel.get(channel, set()))
