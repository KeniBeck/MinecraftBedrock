"""Implementaciones en memoria de IAM para tests (Fase C paso 8).

Mismo criterio que Server/Console: los tests unitarios usan dobles en memoria;
producción inyecta las implementaciones Postgres vía el container.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.modules.iam.application.ports import AuditEntry, Session, SessionStorePort
from app.modules.iam.domain.role import BuiltinRole, ServerMembership
from app.modules.iam.domain.user import User


class InMemoryIamRepository:
    """``IamRepositoryPort`` en memoria con dicts por tabla."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._roles: dict[str, set[str]] = {}
        self._memberships: dict[tuple[str, str], ServerMembership] = {}

    async def save(self, user: User) -> None:
        self._users[user.id] = user

    async def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._users.values() if u.username == username), None)

    async def add_global_role(self, user_id: str, role: BuiltinRole) -> None:
        self._roles.setdefault(user_id, set()).add(role.value)
        user = self._users.get(user_id)
        if user is not None:
            user.roles.add(role)

    async def add_membership(self, user_id: str, server_id: str, role: BuiltinRole) -> None:
        self._memberships[(server_id, user_id)] = ServerMembership(server_id, user_id, role)

    async def list_memberships(self, user_id: str) -> Sequence[ServerMembership]:
        return [m for m in self._memberships.values() if m.user_id == user_id]

    async def touch_last_login(self, user_id: str, at: datetime) -> None:
        user = self._users.get(user_id)
        if user is not None:
            user.last_login_at = at


class InMemorySessionStore(SessionStorePort):
    """``SessionStorePort`` en memoria."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._by_hash: dict[str, Session] = {}

    async def create(self, session: Session) -> None:
        self._sessions[session.id] = session
        self._by_hash[session.token_hash] = session

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        return self._by_hash.get(token_hash)

    async def revoke(self, session_id: str, at: datetime) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            revoked = Session(
                id=session.id,
                user_id=session.user_id,
                token_hash=session.token_hash,
                expires_at=session.expires_at,
                created_at=session.created_at,
                revoked_at=at,
                ip=session.ip,
                ua=session.ua,
            )
            self._sessions[session_id] = revoked
            self._by_hash[revoked.token_hash] = revoked


class InMemoryAuditStore:
    """``AuditStorePort`` en memoria (para testear el log sin BBDD)."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    async def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


__all__ = [
    "InMemoryAuditStore",
    "InMemoryIamRepository",
    "InMemorySessionStore",
]
