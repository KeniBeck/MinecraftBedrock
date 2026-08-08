"""Tests del ``EventDispatcher`` (bus → canales, Fase H §16.13).

Verifica el enrutado de un ``DomainEvent`` a su canal, la numeración con
``seq`` global vía ``EventLog`` y la difusión a las conexiones suscritas.
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.access import Identity
from app.modules.notification.application.connection_manager import (
    ClientConnection,
    ConnectionManager,
)
from app.modules.notification.application.event_dispatcher import (
    EventDispatcher,
    resolve_channels,
)
from app.modules.notification.domain.repository import EventLogEntry
from app.modules.notification.infrastructure.memory import InMemoryEventLogRepository


def make_connection(manager: ConnectionManager, uid: str = "u1") -> ClientConnection:
    connection = ClientConnection(
        connection_id=f"conn-{uid}", identity=Identity(id=uid, username="u", roles=("viewer",))
    )
    manager.register(connection)
    return connection


def drain(buffer: Any) -> list[dict[str, Any]]:
    out = []
    while not buffer.empty():
        item = buffer.get_nowait()
        if item:
            out.append(item)
    return out


class TestEventDispatcher:
    async def test_evento_con_server_id_va_a_su_canal(self) -> None:
        manager = ConnectionManager()
        c1 = make_connection(manager, "u1")
        c2 = make_connection(manager, "u2")
        log = InMemoryEventLogRepository()
        dispatcher = EventDispatcher(connections=manager, event_log=log)

        manager.subscribe("conn-u1", "server:s1")
        manager.subscribe("conn-u2", "server:s2")

        await dispatcher._forward(
            DomainEvent(type="SERVER.STARTED", server_id="s1", payload={"m": 1})
        )

        received = drain(c1.buffer)
        assert len(received) == 1
        envelope = received[0]
        assert envelope["event"] == "SERVER.STARTED"
        assert envelope["scope"] == "server"
        assert envelope["server_id"] == "s1"
        assert envelope["seq"] == 1
        assert drain(c2.buffer) == []

    async def test_evento_sin_server_va_a_global(self) -> None:
        manager = ConnectionManager()
        c1 = make_connection(manager, uid="u1")
        log = InMemoryEventLogRepository()
        dispatcher = EventDispatcher(connections=manager, event_log=log)
        manager.subscribe("conn-u1", "global")
        await dispatcher._forward(DomainEvent(type="SYS.HEALTH", payload={"ok": True}))
        assert drain(c1.buffer)[0]["scope"] == "global"

    async def test_evento_iam_va_al_canal_del_actor(self) -> None:
        manager = ConnectionManager()
        c1 = make_connection(manager, uid="u1")
        log = InMemoryEventLogRepository()
        dispatcher = EventDispatcher(connections=manager, event_log=log)
        manager.subscribe("conn-u1", "user:u1")
        await dispatcher._forward(
            DomainEvent(type="IAM.USER_ROLE_CHANGED", actor_id="u1", payload={"x": 1})
        )
        assert drain(c1.buffer)[0]["scope"] == "user"

    async def test_forward_persiste_en_event_log(self) -> None:
        manager = ConnectionManager()
        log = InMemoryEventLogRepository()
        dispatcher = EventDispatcher(connections=manager, event_log=log)
        await dispatcher._forward(DomainEvent(type="SERVER.CREATED", server_id="s1"))
        events = await log.get_events_since(0, scope="server", server_id="s1")
        assert [(e.seq, e.event_type) for e in events] == [(1, "SERVER.CREATED")]

    async def test_en_on_dispatcher_nunca_rompe_al_bus(self) -> None:
        bus = InProcessEventBus()
        manager = ConnectionManager()

        class BrokenLog:
            async def next_seq(self) -> int:
                raise RuntimeError("boom")

            async def append(self, entry: EventLogEntry) -> None:  # noqa: ARG002
                del entry
                raise RuntimeError("boom")

            async def get_events_since(
                self,
                last_seq: int,
                *,
                scope: str | None = None,
                server_id: str | None = None,
                user_id: str | None = None,
                limit: int = 1000,
            ) -> list[EventLogEntry]:
                del last_seq, scope, server_id, user_id, limit
                return []

            async def latest_seq(self) -> int:
                return 0

        dispatcher = EventDispatcher(connections=manager, event_log=BrokenLog())
        bus.subscribe("*", dispatcher.handler())
        # no debe lanzar: el error se loguea y no propaga al bus
        await bus.publish(DomainEvent(type="SERVER.STARTED", server_id="s1"))


class TestResolveChannels:
    def test_server_id_prioriza_canal_server(self) -> None:
        channels = resolve_channels(DomainEvent(type="TASK.STARTED", server_id="s1"))
        assert channels == {"server:s1"}

    def test_sin_server_id_y_actor_iam_va_a_user(self) -> None:
        channels = resolve_channels(DomainEvent(type="AUTH.LOGIN_SUCCESS", actor_id="u1"))
        assert channels == {"user:u1"}

    def test_global_cuando_no_hay_contexto(self) -> None:
        channels = resolve_channels(DomainEvent(type="HEALTH.OK"))
        assert channels == {"global"}
