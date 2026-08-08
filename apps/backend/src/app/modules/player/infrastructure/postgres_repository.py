"""Repositorio durable de Player sobre Postgres (Fase E paso 11).

Implementa ``PlayerRepositoryPort`` y ``PlayerBanRepositoryPort`` sin tocar el
contrato de dominio: una sesión por operación; ``save_player``/
``save_session``/``save_*_ban`` hacen upsert (las entidades son la autoridad
del estado). Sin FKs a otros módulos.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.player.domain.bans import GlobalBan, ServerBan, normalize_gamertag
from app.modules.player.domain.player import Player
from app.modules.player.domain.session import PlaySession
from app.modules.player.infrastructure.models import (
    GlobalBanRow,
    PlayerRow,
    PlaySessionRow,
    ServerBanRow,
)
from app.modules.player.infrastructure.serialization import (
    global_ban_from_row,
    global_ban_to_row,
    player_from_row,
    player_to_row,
    server_ban_from_row,
    server_ban_to_row,
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

    async def list_open_sessions_by_xuid(self, xuid: str) -> list[PlaySession]:
        stmt = select(PlaySessionRow).where(
            PlaySessionRow.xuid == xuid,
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


def _now() -> datetime:
    return datetime.now(UTC)


class PostgresPlayerBanRepository:
    """Persistencia de bans (globales y por servidor) en ``player_*_bans``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # -- global -----------------------------------------------------------

    async def get_global_ban(self, ban_id: str) -> GlobalBan | None:
        async with self._session_factory() as session:
            row = await session.get(GlobalBanRow, ban_id)
        return global_ban_from_row(row) if row is not None else None

    async def get_global_ban_by_gamertag(self, gamertag: str) -> GlobalBan | None:
        key = normalize_gamertag(gamertag)
        stmt = select(GlobalBanRow).where(func.lower(GlobalBanRow.gamertag) == key).limit(1)
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return global_ban_from_row(row) if row is not None else None

    async def get_active_global_ban_by_xuid(self, xuid: str) -> GlobalBan | None:
        stmt = (
            select(GlobalBanRow)
            .where(
                GlobalBanRow.xuid == xuid,
                or_(GlobalBanRow.expires_at.is_(None), GlobalBanRow.expires_at > _now()),
            )
            .limit(1)
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return global_ban_from_row(row) if row is not None else None

    async def get_active_global_ban_by_gamertag(self, gamertag: str) -> GlobalBan | None:
        key = normalize_gamertag(gamertag)
        stmt = (
            select(GlobalBanRow)
            .where(
                func.lower(GlobalBanRow.gamertag) == key,
                or_(GlobalBanRow.expires_at.is_(None), GlobalBanRow.expires_at > _now()),
            )
            .limit(1)
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return global_ban_from_row(row) if row is not None else None

    async def save_global_ban(self, ban: GlobalBan) -> None:
        values = global_ban_to_row(ban)
        stmt = pg_insert(GlobalBanRow).values(**values)
        update = {key: getattr(stmt.excluded, key) for key in values}
        stmt = stmt.on_conflict_do_update(index_elements=[GlobalBanRow.id], set_=update)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def delete_global_ban(self, ban_id: str) -> bool:
        stmt = delete(GlobalBanRow).where(GlobalBanRow.id == ban_id)
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            await session.commit()
        return cast(int, result.rowcount) > 0  # type: ignore[attr-defined]

    # -- por servidor -----------------------------------------------------

    async def get_server_ban(self, server_id: str, ban_id: str) -> ServerBan | None:
        stmt = select(ServerBanRow).where(
            ServerBanRow.server_id == server_id,
            ServerBanRow.id == ban_id,
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return server_ban_from_row(row) if row is not None else None

    async def get_server_ban_by_gamertag(self, server_id: str, gamertag: str) -> ServerBan | None:
        key = normalize_gamertag(gamertag)
        stmt = (
            select(ServerBanRow)
            .where(
                ServerBanRow.server_id == server_id,
                func.lower(ServerBanRow.gamertag) == key,
            )
            .limit(1)
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return server_ban_from_row(row) if row is not None else None

    async def get_active_server_ban_by_xuid(self, server_id: str, xuid: str) -> ServerBan | None:
        stmt = (
            select(ServerBanRow)
            .where(
                ServerBanRow.server_id == server_id,
                ServerBanRow.xuid == xuid,
                or_(ServerBanRow.expires_at.is_(None), ServerBanRow.expires_at > _now()),
            )
            .limit(1)
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return server_ban_from_row(row) if row is not None else None

    async def get_active_server_ban_by_gamertag(
        self, server_id: str, gamertag: str
    ) -> ServerBan | None:
        key = normalize_gamertag(gamertag)
        stmt = (
            select(ServerBanRow)
            .where(
                ServerBanRow.server_id == server_id,
                func.lower(ServerBanRow.gamertag) == key,
                or_(ServerBanRow.expires_at.is_(None), ServerBanRow.expires_at > _now()),
            )
            .limit(1)
        )
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return server_ban_from_row(row) if row is not None else None

    async def save_server_ban(self, ban: ServerBan) -> None:
        values = server_ban_to_row(ban)
        stmt = pg_insert(ServerBanRow).values(**values)
        update = {key: getattr(stmt.excluded, key) for key in values}
        stmt = stmt.on_conflict_do_update(index_elements=[ServerBanRow.id], set_=update)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def delete_server_ban(self, server_id: str, ban_id: str) -> bool:
        stmt = delete(ServerBanRow).where(
            ServerBanRow.server_id == server_id,
            ServerBanRow.id == ban_id,
        )
        async with self._session_factory() as session:
            result = await session.execute(stmt)
            await session.commit()
        return cast(int, result.rowcount) > 0  # type: ignore[attr-defined]
