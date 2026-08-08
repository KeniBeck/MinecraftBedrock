"""Integración opt-in de Player contra Postgres real (Fase E paso 11).

Usa la fixture ``db_session_factory`` (mismo criterio que Server/IAM/Console/
Configuration): requiere ``BEDROCK_PANEL_TEST_DATABASE_URL``; sin BBDD se
salta limpio.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.modules.player.domain.bans import GlobalBan, ServerBan
from app.modules.player.domain.player import Player
from app.modules.player.domain.session import PlaySession, SessionEndReason
from app.modules.player.infrastructure.postgres_repository import (
    PostgresPlayerBanRepository,
    PostgresPlayerRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

NOW = datetime(2026, 1, 1, tzinfo=UTC)
XUID = "2535467050498296"

pytestmark = pytest.mark.integration


async def test_roundtrip_jugador_y_upsert(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresPlayerRepository(db_session_factory)
    await repo.save_player(
        Player(
            xuid=XUID,
            name="Steve",
            first_seen_at=NOW,
            last_seen_at=NOW,
            playtime_seconds=0,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    loaded = await repo.get_player(XUID)
    assert loaded is not None
    assert loaded.name == "Steve"
    assert await repo.get_player("no-existe") is None

    await repo.save_player(
        Player(
            xuid=XUID,
            name="Steve Renombrado",
            first_seen_at=NOW,
            last_seen_at=NOW + timedelta(minutes=5),
            playtime_seconds=150,
            created_at=NOW,
            updated_at=NOW + timedelta(minutes=5),
        )
    )
    updated = await repo.get_player(XUID)
    assert updated is not None and updated.name == "Steve Renombrado"
    assert updated.playtime_seconds == 150


async def test_get_player_by_name_devuelve_el_mas_reciente(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresPlayerRepository(db_session_factory)
    later = NOW + timedelta(hours=2)
    await repo.save_player(
        Player(
            xuid=XUID,
            name="Steve",
            first_seen_at=NOW,
            last_seen_at=NOW,
            playtime_seconds=0,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    await repo.save_player(
        Player(
            xuid="2535467050498297",
            name="Steve",
            first_seen_at=later,
            last_seen_at=later,
            playtime_seconds=0,
            created_at=later,
            updated_at=later,
        )
    )

    found = await repo.get_player_by_name("Steve")

    assert found is not None and found.xuid == "2535467050498297"
    assert await repo.get_player_by_name("desconocido") is None


async def test_sesiones_open_close_y_presencia_por_servidor(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresPlayerRepository(db_session_factory)
    session = PlaySession(
        id="ps-1",
        server_id="srv-it-1",
        xuid=XUID,
        joined_at=NOW,
    )
    await repo.save_session(session)

    opened = await repo.get_open_session("srv-it-1", XUID)
    assert opened is not None
    assert opened.left_at is None

    closed = PlaySession(
        id="ps-1",
        server_id="srv-it-1",
        xuid=XUID,
        joined_at=NOW,
        left_at=NOW + timedelta(minutes=2),
        reason=SessionEndReason.LEFT,
        playtime_seconds=120,
    )
    await repo.save_session(closed)

    assert await repo.get_open_session("srv-it-1", XUID) is None
    assert await repo.list_open_sessions("srv-it-1") == []


async def test_list_sessions_por_jugador(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresPlayerRepository(db_session_factory)
    for index, hours in enumerate((1, 2, 3)):
        await repo.save_session(
            PlaySession(
                id=f"ps-list-{index}",
                server_id="srv-it-1",
                xuid=XUID,
                joined_at=NOW + timedelta(hours=hours),
            )
        )

    sessions = await repo.list_sessions(XUID, limit=10)

    assert [s.id for s in sessions] == ["ps-list-2", "ps-list-1", "ps-list-0"]
    assert await repo.list_sessions("no-existe") == []


async def test_bans_globales_roundtrip_y_lookups(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresPlayerBanRepository(db_session_factory)
    ban = GlobalBan(
        id="gb-1",
        xuid=XUID,
        gamertag="Steve",
        reason="spam",
        banned_by="admin-1",
        created_at=NOW,
    )
    await repo.save_global_ban(ban)

    by_id = await repo.get_global_ban("gb-1")
    assert by_id is not None and by_id.gamertag == "Steve"
    assert await repo.get_active_global_ban_by_xuid(XUID) is not None
    assert await repo.get_active_global_ban_by_gamertag("steve") is not None  # case-insensitive
    assert await repo.get_active_global_ban_by_gamertag("alex") is None

    expired = GlobalBan(
        id="gb-2",
        gamertag="Alex",
        reason="spam",
        banned_by="admin-1",
        created_at=NOW,
        expires_at=NOW - timedelta(minutes=1),
    )
    await repo.save_global_ban(expired)
    assert await repo.get_active_global_ban_by_gamertag("Alex") is None

    assert await repo.delete_global_ban("gb-1") is True
    assert await repo.get_global_ban("gb-1") is None


async def test_bans_por_servidor_roundtrip_y_lookups(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresPlayerBanRepository(db_session_factory)
    ban = ServerBan(
        id="sb-1",
        server_id="srv-it-1",
        xuid=XUID,
        gamertag="Steve",
        reason="cheats",
        banned_by="admin-1",
        created_at=NOW,
    )
    await repo.save_server_ban(ban)

    assert await repo.get_server_ban("srv-it-1", "sb-1") is not None
    assert await repo.get_active_server_ban_by_xuid("srv-it-1", XUID) is not None
    assert await repo.get_active_server_ban_by_gamertag("srv-it-1", "steve") is not None
    assert await repo.get_active_server_ban_by_xuid("srv-it-2", XUID) is None  # otro server

    assert await repo.delete_server_ban("srv-it-1", "sb-1") is True
    assert await repo.delete_server_ban("srv-it-1", "sb-1") is False
