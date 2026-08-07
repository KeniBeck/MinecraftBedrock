"""Repositorio durable de World sobre Postgres (Fase E paso 12).

Implementa ``WorldRepositoryPort`` sin tocar el contrato de dominio: una
sesión por operación; ``save_world`` hace upsert (la entidad es la autoridad
del estado). ``deactivate_worlds`` se hace con un UPDATE en una sola
sentencia para que la exclusividad de ``activated`` sea atómica por servidor.
"""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.world.domain.world import World
from app.modules.world.infrastructure.models import WorldRow
from app.modules.world.infrastructure.serialization import world_from_row, world_to_row


class PostgresWorldRepository:
    """Persistencia de metadata de mundos en ``world_metadata``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_world(self, server_id: str, name: str) -> World | None:
        stmt = select(WorldRow).where(
            WorldRow.server_id == server_id,
            WorldRow.name == name,
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return world_from_row(row) if row is not None else None

    async def list_worlds(self, server_id: str) -> list[World]:
        stmt = select(WorldRow).where(WorldRow.server_id == server_id).order_by(WorldRow.name)
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [world_from_row(row) for row in rows]

    async def save_world(self, world: World) -> None:
        values = world_to_row(world)
        stmt = pg_insert(WorldRow).values(**values)
        update_map = {key: getattr(stmt.excluded, key) for key in values}
        stmt = stmt.on_conflict_do_update(
            index_elements=[WorldRow.id],
            set_=update_map,
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def delete_world(self, server_id: str, name: str) -> None:
        stmt = delete(WorldRow).where(
            WorldRow.server_id == server_id,
            WorldRow.name == name,
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def deactivate_worlds(self, server_id: str) -> None:
        stmt = update(WorldRow).where(WorldRow.server_id == server_id).values(activated=False)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()
