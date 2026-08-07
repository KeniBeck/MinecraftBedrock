"""Integración de ``PostgresServerRepository`` (Fase A paso 2, opt-in).

Se ejecutan con ``uv run pytest -m integration``; requieren Postgres de test
(``BEDROCK_PANEL_TEST_DATABASE_URL``) y se saltan si no está disponible.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.kernel.ports.runtime import RuntimeSpec, ServerState
from app.modules.server.domain.errors import ServerNotFoundError
from app.modules.server.domain.server import Server, ServerId
from app.modules.server.infrastructure.postgres_repository import PostgresServerRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_server(server_id: str, name: str, state: ServerState = ServerState.CREATED) -> Server:
    return Server(
        id=ServerId(server_id),
        name=name,
        spec=RuntimeSpec(
            image="itzg/minecraft-bedrock-server",
            tag="latest",
            version="1.20.0",
            environment={"MOTD": name},
        ),
        state=state,
        runtime_id="r-" + server_id,
        created_at=NOW,
        updated_at=NOW,
    )


async def test_save_get_roundtrip(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresServerRepository(db_session_factory)
    server = make_server("srv-1", "Survival")

    await repo.save(server)
    restored = await repo.get(ServerId("srv-1"))

    assert restored is not None
    assert restored.id.value == "srv-1"
    assert restored.name == "Survival"
    assert restored.state == ServerState.CREATED
    assert restored.spec == server.spec
    assert restored.created_at == NOW
    assert restored.runtime_id == "r-srv-1"


async def test_get_missing_devuelve_none(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresServerRepository(db_session_factory)
    assert await repo.get(ServerId("no-existe")) is None


async def test_get_required_lanza_not_found(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresServerRepository(db_session_factory)
    with pytest.raises(ServerNotFoundError):
        await repo.get_required(ServerId("no-existe"))


async def test_save_actualiza_en_upsert(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresServerRepository(db_session_factory)
    server = make_server("srv-1", "Survival")
    await repo.save(server)

    server.state = ServerState.RUNNING
    server.updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    server.runtime_id = "r-nuevo"
    await repo.save(server)

    restored = await repo.get(ServerId("srv-1"))
    assert restored is not None
    assert restored.state == ServerState.RUNNING
    assert restored.runtime_id == "r-nuevo"
    assert restored.updated_at == datetime(2026, 1, 2, tzinfo=UTC)


async def test_list_all_devuelve_todos_ordenados(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresServerRepository(db_session_factory)
    await repo.save(make_server("srv-b", "Beta"))
    await repo.save(make_server("srv-a", "Alpha"))

    servers = await repo.list_all()

    assert [server.id.value for server in servers] == ["srv-a", "srv-b"]
