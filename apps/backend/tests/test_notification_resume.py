"""Tests del ``ResumeHandler`` (reenvío por ``seq``, TDD §13.4)."""

from __future__ import annotations

from app.modules.notification.application.resume_handler import ResumeHandler
from app.modules.notification.infrastructure.memory import InMemoryEventLogRepository


class TestResumeHandler:
    async def test_reenvia_eventos_posteriores_al_last_seq(self) -> None:
        log = InMemoryEventLogRepository()
        log.seed("SERVER.CREATED", "server", server_id="s1")  # seq 1
        log.seed("SERVER.STARTED", "server", server_id="s1")  # seq 2
        log.seed("SERVER.STARTING", "server", server_id="s1")  # seq 3

        resume = ResumeHandler(log, limit=1000)
        result = await resume.resume(1, ["server:s1"])

        assert result.exceeded is False
        events = [e["event"] for e in result.envelopes]
        assert events == ["SERVER.STARTED", "SERVER.STARTING"]
        assert [e["seq"] for e in result.envelopes] == [2, 3]

    async def test_filtra_por_servidor(self) -> None:
        log = InMemoryEventLogRepository()
        log.seed("SERVER.CREATED", "server", server_id="s1")  # seq 1
        log.seed("SERVER.CREATED", "server", server_id="s2")  # seq 2

        resume = ResumeHandler(log, limit=1000)
        result = await resume.resume(0, ["server:s1"])
        events = [e["event"] for e in result.envelopes]
        assert events == ["SERVER.CREATED"]
        assert result.envelopes[0]["server_id"] == "s1"

    async def test_limite_trunca_y_marca_exceeded(self) -> None:
        log = InMemoryEventLogRepository()
        for _ in range(10):
            log.seed("SERVER.STARTED", "server", server_id="s1")

        resume = ResumeHandler(log, limit=4)
        result = await resume.resume(0, ["server:s1"])
        assert result.exceeded is True
        assert len(result.envelopes) == 4

    async def test_varios_canales_se_mezclan_ordenados(self) -> None:
        log = InMemoryEventLogRepository()
        log.seed("SERVER.CREATED", "server", server_id="s1")  # seq 1
        log.seed("HEALTH.OK", "global")  # seq 2
        log.seed("SERVER.STARTED", "server", server_id="s1")  # seq 3

        resume = ResumeHandler(log, limit=100)
        result = await resume.resume(0, ["server:s1", "global"])
        assert [e["seq"] for e in result.envelopes] == [1, 2, 3]

    async def test_last_seq_actual_descarta_todo(self) -> None:
        log = InMemoryEventLogRepository()
        log.seed("SERVER.CREATED", "server", server_id="s1")  # seq 1
        resume = ResumeHandler(log, limit=100)
        result = await resume.resume(10, ["server:s1"])
        assert result.envelopes == []
