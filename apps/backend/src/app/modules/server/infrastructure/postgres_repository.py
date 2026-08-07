"""Repositorio durable de ``Server`` sobre Postgres (Fase A paso 2).

Implementa ``ServerRepositoryPort`` sin tocar el contrato de dominio. Cada
operación usa una sesión del pool (una sesión por operación); ``save`` hace un
upsert (``INSERT ... ON CONFLICT``) porque el agregado es la autoridad del
estado. La conexión es perezosa: el repositorio no abre socket al construirse.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.server.domain.errors import ServerNotFoundError
from app.modules.server.domain.server import Server, ServerId
from app.modules.server.infrastructure.models import ServerRow
from app.modules.server.infrastructure.serialization import server_from_row, server_to_row


class PostgresServerRepository:
    """Persistencia del agregado ``Server`` en la tabla ``server_servers``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, server: Server) -> None:
        values = server_to_row(server)
        stmt = pg_insert(ServerRow).values(**values)
        update = {key: getattr(stmt.excluded, key) for key in values}
        stmt = stmt.on_conflict_do_update(index_elements=[ServerRow.id], set_=update)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def get(self, server_id: ServerId) -> Server | None:
        async with self._session_factory() as session:
            row = await session.get(ServerRow, server_id.value)
        return server_from_row(row) if row is not None else None

    async def get_required(self, server_id: ServerId) -> Server:
        server = await self.get(server_id)
        if server is None:
            raise ServerNotFoundError(
                f"Servidor no encontrado: {server_id.value}",
                context={"server_id": server_id.value},
            )
        return server

    async def list_all(self) -> Sequence[Server]:
        async with self._session_factory() as session:
            result = await session.execute(select(ServerRow).order_by(ServerRow.name))
            rows = result.scalars().all()
        return [server_from_row(row) for row in rows]
