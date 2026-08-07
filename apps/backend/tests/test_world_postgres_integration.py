"""Integración opt-in de World contra Postgres real (Fase E paso 12).

Usa la fixture ``db_session_factory`` (mismo criterio que Server/IAM/Console/
Configuration/Player): requiere ``BEDROCK_PANEL_TEST_DATABASE_URL``; sin BBDD
se salta limpio.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.modules.world.domain.world import World
from app.modules.world.infrastructure.postgres_repository import PostgresWorldRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

NOW = datetime(2026, 1, 1, tzinfo=UTC)

pytestmark = pytest.mark.integration


def make_world(
    *,
    name: str,
    server_id: str = "srv-it-1",
    activated: bool = False,
    updated: datetime = NOW,
) -> World:
    return World(
        id=f"world-{name}",
        server_id=server_id,
        name=name,
        level_name=name,
        size_bytes=1024,
        activated=activated,
        created_at=NOW,
        updated_at=updated,
    )


async def test_roundtrip_y_upsert(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresWorldRepository(db_session_factory)
    await repo.save_world(make_world(name="Alpha"))

    loaded = await repo.get_world("srv-it-1", "Alpha")
    assert loaded is not None
    assert loaded.name == "Alpha"
    assert loaded.activated is False
    assert await repo.get_world("srv-it-1", "Nope") is None

    await repo.save_world(
        make_world(name="Alpha", activated=True, updated=NOW + timedelta(minutes=5))
    )
    updated = await repo.get_world("srv-it-1", "Alpha")
    assert updated is not None and updated.activated is True


async def test_list_worlds_por_servidor(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresWorldRepository(db_session_factory)
    await repo.save_world(make_world(name="Beta"))
    await repo.save_world(make_world(name="Alpha"))
    await repo.save_world(make_world(name="Gamma", server_id="srv-it-2"))

    worlds = await repo.list_worlds("srv-it-1")

    assert [w.name for w in worlds] == ["Alpha", "Beta"]


async def test_delete_y_deactivate_excluyente(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresWorldRepository(db_session_factory)
    await repo.save_world(make_world(name="Alpha", activated=True))
    await repo.save_world(make_world(name="Beta"))

    await repo.deactivate_worlds("srv-it-1")

    alpha = await repo.get_world("srv-it-1", "Alpha")
    beta = await repo.get_world("srv-it-1", "Beta")
    assert alpha is not None and alpha.activated is False
    assert beta is not None and beta.activated is False

    await repo.delete_world("srv-it-1", "Alpha")

    assert await repo.get_world("srv-it-1", "Alpha") is None
    assert await repo.get_world("srv-it-1", "Beta") is not None
