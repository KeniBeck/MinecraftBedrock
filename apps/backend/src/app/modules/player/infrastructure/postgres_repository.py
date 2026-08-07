"""Repositorio durable de Player sobre Postgres (Fase E paso 11).

Implementa ``PlayerRepositoryPort`` sin tocar el contrato de dominio: una
sesión por operación; ``save_player``/``save_session`` hacen upsert (las
entidades son la autoridad del estado). Sin FKs a otros módulos.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.player.domain.player import Player
from app.modules.player.domain.session import PlaySession
from app.modules.player.infrastructure.models import PlayerRow, PlaySessionRow
from app.modules.player.infrastructure.serialization import (
    player_from_row,
    player_to_row,
    session_from_row,
    session_to_row,
)


class PostgresPlayerRepository:
    """Persistencia de jugadores y sesiones en ``player_players``/``player_sessions``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_player(self, xuid: str) -> Player | None:
        async with self._session_factory() as session:
            row = await session.get(PlayerRow, xuid)
        return player_from_row(row) if row is not None else None

    async def get_player_by_name(self, name: str) -> Player | None:
        stmt = (
            select(PlayerRow)
            .where(PlayerRow.name == name)
            .order_by(PlayerRow.last_seen_at.desc())
            .limit(1)
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return player_from_row(row) if row is not None else None

    async def save_player(self, player: Player) -> None:
        values = player_to_row(player)
        stmt = pg_insert(PlayerRow).values(**values)
        update = {key: getattr(stmt.excluded, key) for key in values}
        stmt = stmt.on_conflict_do_update(index_elements=[PlayerRow.xuid], set_=update)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_open_session(self, server_id: str, xuid: str) -> PlaySession | None:
        stmt = (
            select(PlaySessionRow)
            .where(
                PlaySessionRow.server_id == server_id,
                PlaySessionRow.xuid == xuid,
                PlaySessionRow.left_at.is_(None),
            )
            .limit(1)
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return session_from_row(row) if row is not None else None

    async def save_session(self, play_session: PlaySession) -> None:
        values = session_to_row(play_session)
        stmt = pg_insert(PlaySessionRow).values(**values)
        update = {key: getattr(stmt.excluded, key) for key in values}
        stmt = stmt.on_conflict_do_update(index_elements=[PlaySessionRow.id], set_=update)
        async with self._session_factory() as db:
            await db.execute(stmt)
            await db.commit()

    async def list_open_sessions(self, server_id: str) -> list[PlaySession]:
        stmt = select(PlaySessionRow).where(
            PlaySessionRow.server_id == server_id,
            PlaySessionRow.left_at.is_(None),
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [session_from_row(row) for row in rows]

    async def list_sessions(self, xuid: str, limit: int = 20) -> list[PlaySession]:
        stmt = (
            select(PlaySessionRow)
            .where(PlaySessionRow.xuid == xuid)
            .order_by(PlaySessionRow.joined_at.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [session_from_row(row) for row in rows]
