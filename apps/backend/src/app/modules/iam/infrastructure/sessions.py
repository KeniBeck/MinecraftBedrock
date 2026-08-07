"""Almacén de sesiones de refresh sobre Postgres (technical-design §14.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.iam.application.ports import Session, SessionStorePort
from app.modules.iam.infrastructure.models import IamSessionRow


class PostgresSessionStore(SessionStorePort):
    """Persistencia de sesiones de refresh en la tabla ``iam_sessions``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, session: Session) -> None:
        row = IamSessionRow(
            id=session.id,
            user_id=session.user_id,
            token_hash=session.token_hash,
            expires_at=session.expires_at,
            revoked_at=session.revoked_at,
            ip=session.ip,
            ua=session.ua,
            created_at=session.created_at,
        )
        async with self._session_factory() as db_session:
            db_session.add(row)
            await db_session.commit()

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        async with self._session_factory() as db_session:
            result = await db_session.execute(
                select(IamSessionRow).where(IamSessionRow.token_hash == token_hash)
            )
            row = result.scalar_one_or_none()
        return self._from_row(row) if row is not None else None

    async def revoke(self, session_id: str, at: datetime) -> None:
        stmt = update(IamSessionRow).where(IamSessionRow.id == session_id).values(revoked_at=at)
        async with self._session_factory() as db_session:
            await db_session.execute(stmt)
            await db_session.commit()

    @staticmethod
    def _from_row(row: IamSessionRow) -> Session:
        return Session(
            id=row.id,
            user_id=row.user_id,
            token_hash=row.token_hash,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            ip=row.ip,
            ua=row.ua,
            created_at=row.created_at,
        )
