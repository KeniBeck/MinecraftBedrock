"""Tests de los handlers de eventos consumidos por IAM (auditoría defensiva)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.modules.iam.application.handlers import (
    BACKUP_FAILED_TOPIC,
    SERVER_CRASHED_TOPIC,
    TASK_FAILED_TOPIC,
    IncidentAuditHandler,
)
from app.modules.iam.application.ports import AuditEntry, AuditStorePort
from app.modules.iam.infrastructure.memory import InMemoryAuditStore
from tests.conftest import FakeTime, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def build_handler(audit: AuditStorePort) -> IncidentAuditHandler:
    return IncidentAuditHandler(audit, SequenceIds("a1"), FakeTime(NOW), "server.crashed", "server")


class FailingAuditStore(AuditStorePort):
    async def record(self, entry: AuditEntry) -> None:
        del entry
        raise RuntimeError("audit roto")

    async def verify(self) -> list[str]:
        return []


class TestIncidentAuditHandler:
    async def test_registra_incidente_con_servidor(self) -> None:
        audit = InMemoryAuditStore()
        handler = build_handler(audit)
        await handler(
            DomainEvent(
                type="SERVER.CRASHED",
                server_id="srv-1",
                actor_id=None,
                payload={"exit_code": 137},
            )
        )
        assert len(audit.entries) == 1
        entry = audit.entries[0]
        assert entry.action == "server.crashed"
        assert entry.resource_id == "srv-1"
        assert entry.result == "failure"
        assert entry.detail == {"exit_code": 137}

    async def test_sin_servidor_no_registra(self) -> None:
        audit = InMemoryAuditStore()
        handler = build_handler(audit)
        await handler(DomainEvent(type="SERVER.CRASHED", server_id=None))
        assert audit.entries == []

    async def test_fallo_de_auditoria_no_propaga(self) -> None:
        handler = build_handler(FailingAuditStore())
        await handler(DomainEvent(type="SERVER.CRASHED", server_id="srv-1"))


class TestBusWiring:
    async def test_suscripciones_registradas_en_el_bus(self) -> None:
        bus = InProcessEventBus()
        audit = InMemoryAuditStore()
        ids = SequenceIds("a1")
        time = FakeTime(NOW)

        topics = [SERVER_CRASHED_TOPIC, TASK_FAILED_TOPIC, BACKUP_FAILED_TOPIC]
        for topic in topics:
            bus.subscribe(topic, IncidentAuditHandler(audit, ids, time, topic, "resource"))

        await bus.publish(DomainEvent(type="SERVER.CRASHED", server_id="srv-1"))
        await bus.publish(DomainEvent(type="TASK.FAILED", server_id="srv-1"))
        await bus.publish(DomainEvent(type="BACKUP.FAILED", server_id="srv-1"))
        assert len(audit.entries) == 3

    async def test_evento_no_suscrito_ignorado(self) -> None:
        bus = InProcessEventBus()
        audit = InMemoryAuditStore()
        bus.subscribe(SERVER_CRASHED_TOPIC, build_handler(audit))
        await bus.publish(DomainEvent(type="SERVER.STARTED", server_id="srv-1"))
        assert audit.entries == []
