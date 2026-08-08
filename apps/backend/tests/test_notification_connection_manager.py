"""Tests del ``ConnectionManager`` (Fase H §16.13).

Cubre registro/baja de conexiones, suscripción/desuscripción por canal y
difusión de envelopes a los suscritos, incluyendo la política de backpressure
(drop-oldest para consola, marca de cierre para críticos).
"""

from __future__ import annotations

from typing import Any

from app.kernel.ports.access import Identity
from app.modules.notification.application.connection_manager import (
    ClientConnection,
    ConnectionManager,
)


def identity(uid: str = "u1") -> Identity:
    return Identity(id=uid, username="usuario", roles=("viewer",))


def make_connection(
    manager: ConnectionManager, uid: str = "u1", max_buffer: int = 3
) -> ClientConnection:
    connection = ClientConnection(
        connection_id=f"conn-{uid}", identity=identity(uid), max_buffer=max_buffer
    )
    manager.register(connection)
    return connection


def envelope(event: str = "SERVER.STARTED", server_id: str | None = "s1") -> dict[str, Any]:
    return {"event": event, "server_id": server_id, "seq": 1, "content": "x"}


def drain(buffer: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    while not buffer.empty():
        item = buffer.get_nowait()
        if item:
            out.append(item)
    return out


class TestConnectionManager:
    def test_subscribe_unsubscribe_track_channels(self) -> None:
        manager = ConnectionManager()
        make_connection(manager)
        manager.subscribe("conn-u1", "server:s1")
        assert manager.subscribed_channels("conn-u1") == {"server:s1"}
        assert manager.connection_ids_for("server:s1") == {"conn-u1"}

        manager.unsubscribe("conn-u1", "server:s1")
        assert manager.subscribed_channels("conn-u1") == set()
        assert manager.connection_ids_for("server:s1") == set()

    def test_unregister_limpia_todos_los_canales(self) -> None:
        manager = ConnectionManager()
        make_connection(manager)
        manager.subscribe("conn-u1", "server:s1")
        manager.subscribe("conn-u1", "global")
        manager.unregister("conn-u1")
        assert manager.connections == {}
        assert manager.connection_ids_for("server:s1") == set()
        assert manager.connection_ids_for("global") == set()

    def test_broadcast_entrega_a_suscritos(self) -> None:
        manager = ConnectionManager()
        c1 = make_connection(manager, "u1")
        c2 = make_connection(manager, "u2")
        manager.subscribe("conn-u1", "server:s1")
        manager.subscribe("conn-u2", "server:s2")

        delivered = manager.broadcast_to_channel("server:s1", envelope())
        assert delivered == 1
        assert drain(c1.buffer) == [envelope()]
        assert drain(c2.buffer) == []

    def test_broadcast_a_dos_canales(self) -> None:
        manager = ConnectionManager()
        c1 = make_connection(manager, uid="u1")
        c2 = make_connection(manager, uid="u2")
        manager.subscribe("conn-u1", "global")
        manager.subscribe("conn-u2", "global")
        n = manager.broadcast_to_channels({"global"}, envelope())
        assert n == 2
        assert len(drain(c1.buffer)) == 1
        assert len(drain(c2.buffer)) == 1

    def test_log_overflow_drop_oldest(self) -> None:
        manager = ConnectionManager()
        c1 = make_connection(manager, uid="u1", max_buffer=2)
        manager.subscribe("conn-u1", "server:s1")
        manager.broadcast_to_channel(
            "server:s1", {"event": "CONSOLE.OUTPUT", "seq": 1, "payload": "a"}
        )
        manager.broadcast_to_channel(
            "server:s1", {"event": "CONSOLE.OUTPUT", "seq": 2, "payload": "b"}
        )
        manager.broadcast_to_channel(
            "server:s1", {"event": "CONSOLE.OUTPUT", "seq": 3, "payload": "c"}
        )
        assert c1.pending == 2
        assert [m["seq"] for m in drain(c1.buffer)] == [2, 3]

    def test_critico_overflow_marca_cierre(self) -> None:
        manager = ConnectionManager()
        c1 = make_connection(manager, uid="u1", max_buffer=1)
        manager.subscribe("conn-u1", "server:s1")
        manager.broadcast_to_channel(
            "server:s1", {"event": "SERVER.STARTED", "seq": 1, "payload": "x"}
        )
        manager.broadcast_to_channel(
            "server:s1", {"event": "SERVER.STOPPED", "seq": 2, "payload": "y"}
        )
        assert c1.close_requested


def test_buffer_vacio_no_bloquea_drain() -> None:
    manager = ConnectionManager()
    connection = make_connection(manager)
    assert drain(connection.buffer) == []
    assert connection.pending == 0
