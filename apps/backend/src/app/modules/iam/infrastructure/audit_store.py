"""Almacén de auditoría tamper-evident sobre Postgres (Fase H paso 18)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.iam.application.audit_chain import compute_audit_hash, verify_chain
from app.modules.iam.application.ports import AuditEntry, AuditLogRecord, AuditStorePort
from app.modules.iam.infrastructure.models import IamAuditLogRow


class PostgresAuditStore(AuditStorePort):
    """Persistencia del audit log en la tabla ``iam_audit_logs`` (hash-chain)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(self, entry: AuditEntry) -> None:
        async with self._session_factory() as session:
            prev_hash = await self._last_hash(session)
            entry_hash = compute_audit_hash(prev_hash, entry)
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
                prev_hash=prev_hash,
                hash=entry_hash,
            )
            session.add(row)
            await session.commit()

    async def verify(self) -> list[str]:
        """Recorre la cadena y devuelve los errores de integridad (vacío = íntegra)."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(IamAuditLogRow).order_by(IamAuditLogRow.created_at, IamAuditLogRow.id)
            )
            rows = result.scalars().all()
        entries = [self._to_entry(row) for row in rows]
        chain = [(row.prev_hash or "", row.hash or "") for row in rows if row.prev_hash is not None]
        if not rows:
            return []
        if len(chain) != len(rows):
            return ["audit: cadena incompleta: faltan hashes en registros previos"]
        return verify_chain(entries, chain)

    async def list(
        self,
        *,
        actor_id: str | None = None,
        action: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLogRecord], int]:
        async with self._session_factory() as session:
            conditions = []
            if actor_id:
                conditions.append(IamAuditLogRow.actor_id == actor_id)
            if action:
                conditions.append(IamAuditLogRow.action.ilike(f"%{action}%"))
            if from_at is not None:
                conditions.append(IamAuditLogRow.created_at >= from_at)
            if to_at is not None:
                conditions.append(IamAuditLogRow.created_at <= to_at)

            total = await session.scalar(
                select(func.count()).select_from(IamAuditLogRow).where(*conditions)
            )
            result = await session.execute(
                select(IamAuditLogRow)
                .where(*conditions)
                .order_by(IamAuditLogRow.created_at.desc(), IamAuditLogRow.id)
                .offset(offset)
                .limit(limit)
            )
            rows = result.scalars().all()
        return [self._to_record(row) for row in rows], int(total or 0)

    @staticmethod
    async def _last_hash(session: AsyncSession) -> str:
        result = await session.execute(
            select(IamAuditLogRow.hash).order_by(IamAuditLogRow.created_at, IamAuditLogRow.id)
        )
        last = result.scalars().all()
        value = last[-1] if last else ""
        return value or ""

    @staticmethod
    def _to_entry(row: IamAuditLogRow) -> AuditEntry:
        return AuditEntry(
            id=row.id,
            actor_id=row.actor_id,
            actor_type=row.actor_type,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            result=row.result,
            detail=row.detail,
            ip=row.ip,
            ua=row.ua,
            created_at=row.created_at,
        )

    @staticmethod
    def _to_record(row: IamAuditLogRow) -> AuditLogRecord:
        return AuditLogRecord(
            id=row.id,
            actor_id=row.actor_id,
            actor_type=row.actor_type,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            result=row.result,
            detail=row.detail,
            ip=row.ip,
            ua=row.ua,
            created_at=row.created_at,
            hash=row.hash,
            prev_hash=row.prev_hash,
        )
