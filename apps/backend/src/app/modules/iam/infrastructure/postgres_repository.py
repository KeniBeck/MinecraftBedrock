"""Repositorio durable de IAM sobre Postgres (Fase C paso 8).

Implementa ``IamRepositoryPort`` sin tocar el contrato de dominio. Cada
operación usa una sesión del pool (una sesión por operación); ``save`` hace un
upsert (``INSERT ... ON CONFLICT``) porque ``User`` es la autoridad del estado.
Los roles globales y las membresías se consultan/insertan por separado.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.iam.domain.role import BuiltinRole, ServerMembership
from app.modules.iam.domain.user import User, UserStatus
from app.modules.iam.infrastructure.models import (
    IamServerMembershipRow,
    IamUserRoleRow,
    IamUserRow,
)


class PostgresIamRepository:
    """Persistencia del agregado ``User`` y sus asociaciones en tablas ``iam_*``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save(self, user: User) -> None:
        stmt = pg_insert(IamUserRow).values(
            id=user.id,
            username=user.username,
            password_hash=user.password_hash,
            display_name=user.display_name,
            status=user.status.value,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            totp_secret=user.totp_secret,
            totp_enabled=user.totp_enabled,
            backup_codes=user.backup_codes,
        )
        update_values = {
            "username": stmt.excluded.username,
            "password_hash": stmt.excluded.password_hash,
            "display_name": stmt.excluded.display_name,
            "status": stmt.excluded.status,
            "last_login_at": stmt.excluded.last_login_at,
            "totp_secret": stmt.excluded.totp_secret,
            "totp_enabled": stmt.excluded.totp_enabled,
            "backup_codes": stmt.excluded.backup_codes,
        }
        stmt = stmt.on_conflict_do_update(index_elements=[IamUserRow.id], set_=update_values)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def get(self, user_id: str) -> User | None:
        async with self._session_factory() as session:
            row = await session.get(IamUserRow, user_id)
            if row is None:
                return None
            roles = await self._load_roles(session, user_id)
        return self._from_row(row, roles)

    async def get_by_username(self, username: str) -> User | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(IamUserRow).where(IamUserRow.username == username)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            roles = await self._load_roles(session, row.id)
        return self._from_row(row, roles)

    async def add_global_role(self, user_id: str, role: BuiltinRole) -> None:
        stmt = (
            pg_insert(IamUserRoleRow)
            .values(user_id=user_id, role=role.value)
            .on_conflict_do_nothing(index_elements=[IamUserRoleRow.user_id, IamUserRoleRow.role])
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def add_membership(self, user_id: str, server_id: str, role: BuiltinRole) -> None:
        stmt = (
            pg_insert(IamServerMembershipRow)
            .values(server_id=server_id, user_id=user_id, role=role.value)
            .on_conflict_do_update(
                index_elements=[
                    IamServerMembershipRow.server_id,
                    IamServerMembershipRow.user_id,
                ],
                set_={"role": role.value},
            )
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def list_memberships(self, user_id: str) -> Sequence[ServerMembership]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(IamServerMembershipRow).where(IamServerMembershipRow.user_id == user_id)
            )
            rows = result.scalars().all()
        return [
            ServerMembership(
                server_id=row.server_id,
                user_id=row.user_id,
                role=BuiltinRole(row.role),
            )
            for row in rows
        ]

    async def touch_last_login(self, user_id: str, at: datetime) -> None:
        stmt = update(IamUserRow).where(IamUserRow.id == user_id).values(last_login_at=at)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def _load_roles(self, session: AsyncSession, user_id: str) -> set[BuiltinRole]:
        result = await session.execute(
            select(IamUserRoleRow.role).where(IamUserRoleRow.user_id == user_id)
        )
        return {BuiltinRole(name) for (name,) in result.all()}

    @staticmethod
    def _from_row(row: IamUserRow, roles: set[BuiltinRole]) -> User:
        return User(
            id=row.id,
            username=row.username,
            password_hash=row.password_hash,
            display_name=row.display_name,
            status=UserStatus(row.status),
            created_at=row.created_at,
            last_login_at=row.last_login_at,
            roles=roles,
            totp_secret=row.totp_secret,
            totp_enabled=row.totp_enabled,
            backup_codes=row.backup_codes,
        )
