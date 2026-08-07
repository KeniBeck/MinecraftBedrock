"""Almacén de auditoría sobre Postgres (log básico, sin hash-chain: Fase H)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.iam.application.ports import AuditEntry, AuditStorePort
from app.modules.iam.infrastructure.models import IamAuditLogRow


class PostgresAuditStore(AuditStorePort):
    """Persistencia del audit log en la tabla ``iam_audit_logs``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(self, entry: AuditEntry) -> None:
        row = IamAuditLogRow(
            id=entry.id,
            actor_id=entry.actor_id,
            actor_type=entry.actor_type,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            result=entry.result,
            detail=entry.detail,
            ip=entry.ip,
            ua=entry.ua,
            created_at=entry.created_at,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
