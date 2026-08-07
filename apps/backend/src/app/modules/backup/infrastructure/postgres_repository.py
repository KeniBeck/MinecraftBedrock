"""Repositorio durable de Backup sobre Postgres (Fase F paso 13).

Implementa ``BackupRepositoryPort`` sin tocar el contrato de dominio: una
sesión por operación; ``save_backup`` hace upsert (la entidad es la autoridad
del estado). ``mark_orphaned`` actualiza por sentencia única los registros de
un mundo eliminado (§9.3).
"""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.backup.domain.backup import Backup
from app.modules.backup.infrastructure.models import BackupRow
from app.modules.backup.infrastructure.serialization import backup_from_row, backup_to_row


class PostgresBackupRepository:
    """Persistencia de registros de backup en ``backup_backups``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_backup(self, backup: Backup) -> None:
        values = backup_to_row(backup)
        stmt = pg_insert(BackupRow).values(**values)
        update_map = {key: getattr(stmt.excluded, key) for key in values}
        stmt = stmt.on_conflict_do_update(
            index_elements=[BackupRow.id],
            set_=update_map,
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_backup(self, backup_id: str) -> Backup | None:
        stmt = select(BackupRow).where(BackupRow.id == backup_id)
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return backup_from_row(row) if row is not None else None

    async def list_backups(
        self,
        server_id: str,
        *,
        world_name: str | None = None,
        limit: int = 50,
    ) -> list[Backup]:
        stmt = select(BackupRow).where(BackupRow.server_id == server_id)
        if world_name is not None:
            stmt = stmt.where(BackupRow.world_name == world_name)
        stmt = stmt.order_by(BackupRow.created_at.desc()).limit(limit)
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [backup_from_row(row) for row in rows]

    async def delete_backup(self, backup_id: str) -> None:
        stmt = delete(BackupRow).where(BackupRow.id == backup_id)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def mark_orphaned(self, server_id: str, world_name: str) -> None:
        stmt = (
            update(BackupRow)
            .where(
                BackupRow.server_id == server_id,
                BackupRow.world_name == world_name,
            )
            .values(orphaned=True)
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()
