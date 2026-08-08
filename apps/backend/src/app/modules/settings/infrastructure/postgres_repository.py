"""Repositorio Settings sobre Postgres (Fase H paso 19, tabla ``settings``).

Upsert por clave; ``set_many`` es atómico (una sesión/transacción). ``get_all``/
``list_full`` ordenan por categoría para una API estable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.settings.infrastructure.models import SettingRow


class PostgresSettingsRepository:
    """Persistencia de ajustes en la tabla ``settings``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, key: str) -> Any | None:
        async with self._session_factory() as session:
            row = await session.get(SettingRow, key)
        return row.value if row is not None else None

    async def set(
        self,
        key: str,
        value: Any,
        category: str,
        description: str | None,
        updated_by: str,
    ) -> None:
        await self.set_many({key: value}, description, updated_by, category=category)

    async def set_many(
        self,
        values: dict[str, Any],
        description: str | None,
        updated_by: str,
        *,
        category: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            for key, value in values.items():
                stmt = pg_insert(SettingRow).values(
                    key=key,
                    value=value,
                    category=category or _category_for(key),
                    description=description,
                    updated_by=updated_by,
                    updated_at=now,
                )
                update_values = {
                    "value": stmt.excluded.value,
                    "category": stmt.excluded.category,
                    "description": stmt.excluded.description,
                    "updated_by": stmt.excluded.updated_by,
                    "updated_at": stmt.excluded.updated_at,
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=[SettingRow.key], set_=update_values
                )
                await session.execute(stmt)
            await session.commit()

    async def delete(self, key: str) -> None:
        from sqlalchemy import delete as sa_delete

        stmt = sa_delete(SettingRow).where(SettingRow.key == key)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(SettingRow.key, SettingRow.value).where(SettingRow.key.in_(keys))
            )
            rows = result.all()
        return {row[0]: row[1] for row in rows}

    async def list_by_category(self, category: str) -> dict[str, Any]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(SettingRow.key, SettingRow.value).where(SettingRow.category == category)
            )
            rows = result.all()
        return {row[0]: row[1] for row in rows}

    async def get_all(self) -> dict[str, Any]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(SettingRow.key, SettingRow.value).order_by(SettingRow.key)
            )
            rows = result.all()
        return {row[0]: row[1] for row in rows}

    async def list_full(self) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(SettingRow).order_by(SettingRow.category, SettingRow.key)
            )
            rows = result.scalars().all()
        return [
            {
                "key": row.key,
                "value": row.value,
                "category": row.category,
                "description": row.description,
                "updated_by": row.updated_by,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]


def _category_for(key: str) -> str:
    from app.modules.settings.domain.defaults import DEFINITIONS_BY_KEY

    definition = DEFINITIONS_BY_KEY.get(key)
    return definition.category if definition is not None else "system"
