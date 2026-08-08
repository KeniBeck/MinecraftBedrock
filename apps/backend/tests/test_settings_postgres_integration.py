"""Integración opt-in de Settings contra Postgres real (Fase H paso 19)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.modules.settings.infrastructure.postgres_repository import PostgresSettingsRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

pytestmark = pytest.mark.integration


async def test_crud_y_listado(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresSettingsRepository(db_session_factory)
    await repo.set("system.log_level", "DEBUG", "system", "nivel", "it-user")
    assert await repo.get("system.log_level") == "DEBUG"

    await repo.set_many({"limits.max_servers": 3, "defaults.tag": "beta"}, "batch", "it-user")
    many = await repo.get_many(["system.log_level", "limits.max_servers", "nope"])
    assert many == {"system.log_level": "DEBUG", "limits.max_servers": 3}

    storage = await repo.list_by_category("system")
    assert storage["system.log_level"] == "DEBUG"

    all_values = await repo.get_all()
    assert all_values["defaults.tag"] == "beta"

    full = await repo.list_full()
    assert len(full) == 3
    assert {item["key"] for item in full} == {
        "system.log_level",
        "limits.max_servers",
        "defaults.tag",
    }

    await repo.delete("defaults.tag")
    assert await repo.get("defaults.tag") is None


async def test_upsert_sobreescribe_y_mantiene_una_fila(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresSettingsRepository(db_session_factory)
    await repo.set("defaults.image", "img-a", "defaults", None, "u1")
    await repo.set("defaults.image", "img-b", "defaults", "segundo", "u1")
    values = await repo.get_all()
    assert values["defaults.image"] == "img-b"
