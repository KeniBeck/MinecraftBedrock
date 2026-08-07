"""Integración opt-in de Configuration contra Postgres real (Fase D paso 10).

Usa la fixture ``db_session_factory`` (mismo criterio que Server/IAM/Console):
requiere ``BEDROCK_PANEL_TEST_DATABASE_URL``; sin BBDD se salta limpio.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from app.modules.configuration.domain.config_profile import ConfigChange, ConfigProfile
from app.modules.configuration.infrastructure.postgres_repository import (
    PostgresConfigurationRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

NOW = datetime(2026, 1, 1, tzinfo=UTC)

pytestmark = pytest.mark.integration


async def test_roundtrip_perfil_y_upsert(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresConfigurationRepository(db_session_factory)
    await repo.save_profile(
        ConfigProfile(
            server_id="cfg-it-1",
            properties={"server-name": "Mi Mundo", "max-players": "10"},
            version="1.20.0",
            config_rev=1,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    loaded = await repo.get_profile("cfg-it-1")
    assert loaded is not None
    assert loaded.properties == {"server-name": "Mi Mundo", "max-players": "10"}
    assert loaded.config_rev == 1
    assert await repo.get_profile("no-existe") is None

    await repo.save_profile(
        ConfigProfile(
            server_id="cfg-it-1",
            properties={"server-name": "Otro"},
            version="1.20.0",
            config_rev=2,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    updated = await repo.get_profile("cfg-it-1")
    assert updated is not None and updated.config_rev == 2
    assert updated.properties == {"server-name": "Otro"}


async def test_historial_append_only(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresConfigurationRepository(db_session_factory)
    for rev in (1, 2, 3):
        await repo.append_change(
            ConfigChange(
                server_id="cfg-it-2",
                config_rev=rev,
                properties={"max-players": str(rev * 5)},
                version="1.20.0",
                changed_at=NOW,
                actor_id="u1",
            )
        )

    history = await repo.history("cfg-it-2", limit=10)

    assert [entry.config_rev for entry in history] == [3, 2, 1]
    assert history[0].properties == {"max-players": "15"}
    assert history[0].actor_id == "u1"
    assert await repo.history("cfg-it-otro") == []
