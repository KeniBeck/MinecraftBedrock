"""Repositorio durable de Template sobre Postgres (Fase G paso 16).

Implementa ``TemplateRepositoryPort`` sin tocar el contrato de dominio: una
sesión por operación; ``save`` hace upsert (la entidad es la autoridad del
estado). El artefacto no vive aquí (va en ``TemplateArchiveStore``); solo la
metadata.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.template.domain.template import Template
from app.modules.template.infrastructure.models import TemplateRow
from app.modules.template.infrastructure.serialization import template_from_row, template_to_row


class PostgresTemplateRepository:
    """Persistencia de la metadata de plantillas en ``template_templates``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, template: Template) -> None:
        values = template_to_row(template)
        stmt = pg_insert(TemplateRow).values(**values)
        update_map = {key: getattr(stmt.excluded, key) for key in values}
        stmt = stmt.on_conflict_do_update(
            index_elements=[TemplateRow.id],
            set_=update_map,
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def get(self, template_id: str) -> Template | None:
        stmt = select(TemplateRow).where(TemplateRow.id == template_id)
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return template_from_row(row) if row is not None else None

    async def get_by_name(self, name: str) -> Template | None:
        stmt = select(TemplateRow).where(TemplateRow.name == name)
        async with self._session_factory() as session:
            row = (await session.execute(stmt)).scalars().first()
        return template_from_row(row) if row is not None else None

    async def list(self) -> list[Template]:
        stmt = select(TemplateRow).order_by(TemplateRow.created_at)
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [template_from_row(row) for row in rows]

    async def delete(self, template_id: str) -> None:
        from sqlalchemy import delete

        stmt = delete(TemplateRow).where(TemplateRow.id == template_id)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()
