"""Integración opt-in del repositorio Backup contra Postgres real (Fase F paso 13).

Usa la fixture ``db_session_factory`` (mismo criterio que Server/IAM/Console/
Configuration/Player/World): requiere ``BEDROCK_PANEL_TEST_DATABASE_URL``; sin
BBDD se salta limpio.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.modules.backup.domain.backup import Backup, BackupState
from app.modules.backup.infrastructure.postgres_repository import PostgresBackupRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

NOW = datetime(2026, 1, 1, tzinfo=UTC)

pytestmark = pytest.mark.integration


def make_backup(
    *,
    backup_id: str,
    world_name: str,
    server_id: str = "srv-it-1",
    created_at: datetime = NOW,
    state: BackupState = BackupState.COMPLETED,
) -> Backup:
    return Backup(
        id=backup_id,
        server_id=server_id,
        world_name=world_name,
        state=state,
        storage_ref=f"{server_id}/{backup_id}.tar.zst",
        created_at=created_at,
        updated_at=created_at,
        size_bytes=1024,
        checksum="abc",
        entries=["level.dat", "levelname.txt"],
    )


async def test_roundtrip_y_upsert(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresBackupRepository(db_session_factory)
    await repo.save_backup(make_backup(backup_id="bk-1", world_name="Alpha"))

    loaded = await repo.get_backup("bk-1")
    assert loaded is not None
    assert loaded.world_name == "Alpha"
    assert loaded.state is BackupState.COMPLETED
    assert await repo.get_backup("nope") is None

    await repo.save_backup(
        make_backup(
            backup_id="bk-1",
            world_name="Alpha",
            state=BackupState.CORRUPT,
            created_at=NOW + timedelta(minutes=5),
        )
    )
    updated = await repo.get_backup("bk-1")
    assert updated is not None and updated.state is BackupState.CORRUPT


async def test_list_backups_filtra_y_ordena(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresBackupRepository(db_session_factory)
    await repo.save_backup(make_backup(backup_id="bk-1", world_name="Alpha", created_at=NOW))
    await repo.save_backup(
        make_backup(
            backup_id="bk-2",
            world_name="Alpha",
            created_at=NOW + timedelta(minutes=10),
        )
    )
    await repo.save_backup(make_backup(backup_id="bk-3", world_name="Beta", server_id="srv-it-2"))

    all_alpha = await repo.list_backups("srv-it-1")
    limited = await repo.list_backups("srv-it-1", limit=1)

    assert [b.id for b in all_alpha] == ["bk-2", "bk-1"]
    assert [b.id for b in limited] == ["bk-2"]


async def test_delete_backup(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresBackupRepository(db_session_factory)
    await repo.save_backup(make_backup(backup_id="bk-1", world_name="Alpha"))

    await repo.delete_backup("bk-1")

    assert await repo.get_backup("bk-1") is None


async def test_mark_orphaned_por_mundo(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresBackupRepository(db_session_factory)
    await repo.save_backup(make_backup(backup_id="bk-1", world_name="Alpha"))
    await repo.save_backup(make_backup(backup_id="bk-2", world_name="Beta"))

    await repo.mark_orphaned("srv-it-1", "Alpha")

    alpha = await repo.get_backup("bk-1")
    beta = await repo.get_backup("bk-2")
    assert alpha is not None and alpha.orphaned is True
    assert beta is not None and beta.orphaned is False
