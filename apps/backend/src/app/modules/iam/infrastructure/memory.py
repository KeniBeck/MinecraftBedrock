"""Implementaciones en memoria de IAM para tests (Fase C paso 8).

Mismo criterio que Server/Console: los tests unitarios usan dobles en memoria;
producción inyecta las implementaciones Postgres vía el container.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.modules.iam.application.audit_chain import compute_audit_hash, verify_chain
from app.modules.iam.application.ports import (
    ApiKey,
    ApiKeyStorePort,
    AuditEntry,
    AuditLogRecord,
    Session,
    SessionStorePort,
)
from app.modules.iam.domain.permissions import (
    PERMISSIONS_SEED,
    ROLE_PERMISSIONS,
    PermissionCode,
)
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

    async def list_users(self) -> Sequence[User]:
        return sorted(
            self._users.values(),
            key=lambda u: (u.created_at, u.id),
            reverse=True,
        )

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._users.values() if u.username == username), None)

    async def add_global_role(self, user_id: str, role: BuiltinRole) -> None:
        self._roles.setdefault(user_id, set()).add(role.value)
        user = self._users.get(user_id)
        if user is not None:
            user.roles.add(role)

    async def replace_global_roles(self, user_id: str, roles: Sequence[BuiltinRole]) -> None:
        self._roles[user_id] = {role.value for role in roles}
        user = self._users.get(user_id)
        if user is not None:
            user.roles = set(roles)

    async def add_membership(self, user_id: str, server_id: str, role: BuiltinRole) -> None:
        self._memberships[(server_id, user_id)] = ServerMembership(server_id, user_id, role)

    async def list_memberships(self, user_id: str) -> Sequence[ServerMembership]:
        return [m for m in self._memberships.values() if m.user_id == user_id]

    async def touch_last_login(self, user_id: str, at: datetime) -> None:
        user = self._users.get(user_id)
        if user is not None:
            user.last_login_at = at


class InMemoryPermissionRepository:
    """``PermissionRepositoryPort`` en memoria con la matriz estática."""

    def __init__(self) -> None:
        self.catalog = list(PERMISSIONS_SEED)

    async def list_permissions(self) -> Sequence[PermissionCode]:
        return self.catalog

    async def permissions_for_role(self, role: BuiltinRole) -> frozenset[str]:
        return ROLE_PERMISSIONS.get(role, frozenset())

    async def seed_catalog(self) -> None:
        return


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
    """``AuditStorePort`` tamper-evident en memoria (cadena de hash)."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []
        self._chain: list[tuple[str, str]] = []

    async def record(self, entry: AuditEntry) -> None:
        prev_hash = self._chain[-1][1] if self._chain else ""
        entry_hash = compute_audit_hash(prev_hash, entry)
        self._chain.append((prev_hash, entry_hash))
        self.entries.append(entry)

    async def verify(self) -> list[str]:
        """Devuelve errores de la cadena (vacío = íntegra)."""
        return verify_chain(self.entries, self._chain)

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
        records = [
            AuditLogRecord(
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
                prev_hash=self._chain[index][0],
                hash=self._chain[index][1],
            )
            for index, entry in enumerate(self.entries)
        ]
        if actor_id:
            records = [r for r in records if r.actor_id == actor_id]
        if action:
            records = [r for r in records if action.lower() in r.action.lower()]
        if from_at is not None:
            records = [r for r in records if r.created_at >= from_at]
        if to_at is not None:
            records = [r for r in records if r.created_at <= to_at]
        records.sort(key=lambda r: (r.created_at, r.id), reverse=True)
        total = len(records)
        return records[offset : offset + limit], total


class InMemoryApiKeyStore(ApiKeyStorePort):
    """``ApiKeyStorePort`` en memoria."""

    def __init__(self) -> None:
        self._keys: dict[str, ApiKey] = {}

    async def create(self, key: ApiKey) -> None:
        self._keys[key.id] = key

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        return next((k for k in self._keys.values() if k.key_hash == key_hash), None)

    async def list_for_user(self, user_id: str) -> list[ApiKey]:
        return [k for k in self._keys.values() if k.user_id == user_id]

    async def revoke(self, key_id: str, user_id: str) -> None:
        key = self._keys.get(key_id)
        if key is not None and key.user_id == user_id:
            del self._keys[key_id]

    async def rotate(self, key_id: str, user_id: str, key_hash: str) -> None:
        key = self._keys.get(key_id)
        if key is not None and key.user_id == user_id:
            self._keys[key_id] = ApiKey(
                id=key.id,
                user_id=key.user_id,
                name=key.name,
                key_hash=key_hash,
                scopes=key.scopes,
                last_used_at=None,
                created_at=key.created_at,
                expires_at=key.expires_at,
            )

    async def touch(self, key_id: str, at: datetime) -> None:
        key = self._keys.get(key_id)
        if key is not None:
            self._keys[key_id] = ApiKey(
                id=key.id,
                user_id=key.user_id,
                name=key.name,
                key_hash=key.key_hash,
                scopes=key.scopes,
                last_used_at=at,
                created_at=key.created_at,
                expires_at=key.expires_at,
            )


__all__ = [
    "InMemoryApiKeyStore",
    "InMemoryAuditStore",
    "InMemoryIamRepository",
    "InMemoryPermissionRepository",
    "InMemorySessionStore",
]
