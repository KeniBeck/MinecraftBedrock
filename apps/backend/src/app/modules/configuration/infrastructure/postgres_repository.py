"""Repositorio durable de Configuration sobre Postgres (Fase D paso 10).

Implementa ``ConfigurationRepositoryPort`` sin tocar el contrato de dominio:
una sesión por operación; ``save_profile`` hace un upsert (el perfil es la
autoridad del estado deseado) y el historial es append-only (ADR-004).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.configuration.domain.config_profile import ConfigChange, ConfigProfile
from app.modules.configuration.infrastructure.models import ConfigHistoryRow, ConfigProfileRow
from app.modules.configuration.infrastructure.serialization import (
    change_from_row,
    profile_from_row,
    profile_to_row,
)


class PostgresConfigurationRepository:
    """Persistencia de perfiles e historial en ``config_profiles``/``config_history``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_profile(self, server_id: str) -> ConfigProfile | None:
        async with self._session_factory() as session:
            row = await session.get(ConfigProfileRow, server_id)
        return profile_from_row(row) if row is not None else None

    async def save_profile(self, profile: ConfigProfile) -> None:
        values = profile_to_row(profile)
        stmt = pg_insert(ConfigProfileRow).values(**values)
        update = {key: getattr(stmt.excluded, key) for key in values}
        stmt = stmt.on_conflict_do_update(index_elements=[ConfigProfileRow.server_id], set_=update)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def append_change(self, change: ConfigChange) -> None:
        async with self._session_factory() as session:
            session.add(
                ConfigHistoryRow(
                    server_id=change.server_id,
                    config_rev=change.config_rev,
                    properties=dict(change.properties),
                    version=change.version,
                    actor_id=change.actor_id,
                    changed_at=change.changed_at,
                )
            )
            await session.commit()

    async def history(self, server_id: str, limit: int = 20) -> list[ConfigChange]:
        stmt = (
            select(ConfigHistoryRow)
            .where(ConfigHistoryRow.server_id == server_id)
            .order_by(ConfigHistoryRow.config_rev.desc())
            .limit(limit)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [change_from_row(row) for row in rows]
