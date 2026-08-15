"""Integración opt-in de IAM contra Postgres real (Fase C paso 8).

Usa la fixture ``db_session_factory`` (mismo criterio que Server/Console):
requiere ``BEDROCK_PANEL_TEST_DATABASE_URL``; sin BBDD se salta limpio.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from app.modules.iam.application.ports import Session
from app.modules.iam.domain.role import BuiltinRole
from app.modules.iam.domain.user import User, UserStatus
from app.modules.iam.infrastructure.audit_store import PostgresAuditStore
from app.modules.iam.infrastructure.password import Argon2PasswordHasher
from app.modules.iam.infrastructure.postgres_repository import PostgresIamRepository
from app.modules.iam.infrastructure.sessions import PostgresSessionStore

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

NOW = datetime(2026, 1, 1, tzinfo=UTC)

pytestmark = pytest.mark.integration


async def test_repositorio_roundtrip_usuario(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresIamRepository(db_session_factory)
    user = User(
        id="iam-it-1",
        username="it-user",
        password_hash="hash-arbitrario",
        display_name="IT User",
        status=UserStatus.ACTIVE,
        created_at=NOW,
    )
    await repo.save(user)

    loaded = await repo.get("iam-it-1")
    assert loaded is not None
    assert loaded.username == "it-user"
    assert loaded.status is UserStatus.ACTIVE
    assert loaded.roles == set()

    by_name = await repo.get_by_username("it-user")
    assert by_name is not None and by_name.id == "iam-it-1"
    assert await repo.get_by_username("no-existe") is None


async def test_roles_y_membresias(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresIamRepository(db_session_factory)
    await repo.save(
        User(
            id="iam-it-2",
            username="it-rol",
            password_hash="x",
            display_name="Rol",
            status=UserStatus.ACTIVE,
            created_at=NOW,
        )
    )
    await repo.add_global_role("iam-it-2", BuiltinRole.OPERATOR)
    await repo.add_global_role("iam-it-2", BuiltinRole.VIEWER)
    await repo.add_membership("iam-it-2", "srv-1", BuiltinRole.OPERATOR)

    user = await repo.get("iam-it-2")
    assert user is not None
    assert user.roles == {BuiltinRole.OPERATOR, BuiltinRole.VIEWER}

    memberships = await repo.list_memberships("iam-it-2")
    assert len(memberships) == 1
    assert memberships[0].server_id == "srv-1"
    assert memberships[0].role is BuiltinRole.OPERATOR

    await repo.add_membership("iam-it-2", "srv-1", BuiltinRole.ADMIN)
    memberships = await repo.list_memberships("iam-it-2")
    assert memberships[0].role is BuiltinRole.ADMIN


async def test_last_login_y_password_real(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresIamRepository(db_session_factory)
    hasher = Argon2PasswordHasher()
    await repo.save(
        User(
            id="iam-it-3",
            username="it-pass",
            password_hash=hasher.hash("s3cret"),
            display_name="Pass",
            status=UserStatus.ACTIVE,
            created_at=NOW,
        )
    )
    await repo.touch_last_login("iam-it-3", NOW)
    loaded = await repo.get("iam-it-3")
    assert loaded is not None
    assert loaded.last_login_at == NOW
    assert hasher.verify("s3cret", loaded.password_hash) is True
    assert hasher.verify("mal", loaded.password_hash) is False


async def test_sesiones_revocables(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = PostgresSessionStore(db_session_factory)
    await store.create(
        Session(
            id="iam-ses-1",
            user_id="iam-it-1",
            token_hash="token-hash-abc",
            expires_at=NOW,
            created_at=NOW,
        )
    )
    session = await store.get_by_token_hash("token-hash-abc")
    assert session is not None and session.user_id == "iam-it-1"
    assert session.is_active

    await store.revoke("iam-ses-1", NOW)
    revoked = await store.get_by_token_hash("token-hash-abc")
    assert revoked is not None and revoked.revoked_at == NOW and revoked.is_active is False

    assert await store.get_by_token_hash("no-existe") is None


async def test_audit_log(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.modules.iam.application.ports import AuditEntry

    store = PostgresAuditStore(db_session_factory)
    await store.record(
        AuditEntry(
            id="iam-aud-1",
            actor_id="iam-it-1",
            actor_type="user",
            action="AUTH.LOGIN_SUCCESS",
            result="success",
            created_at=NOW,
            resource_type="user",
            resource_id="iam-it-1",
            detail={"username": "it-user"},
        )
    )
    from sqlalchemy import select

    from app.modules.iam.infrastructure.models import IamAuditLogRow

    async with db_session_factory() as session:
        result = await session.execute(select(IamAuditLogRow))
        rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "AUTH.LOGIN_SUCCESS"
    assert rows[0].detail == {"username": "it-user"}


async def test_audit_tamper_evident_verifica_cadena(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.modules.iam.application.ports import AuditEntry
    from app.modules.iam.infrastructure.audit_store import PostgresAuditStore

    store = PostgresAuditStore(db_session_factory)
    for index in range(3):
        await store.record(
            AuditEntry(
                id=f"iam-hash-{index}",
                actor_id="iam-it-1",
                actor_type="user",
                action="AUTH.LOGIN_SUCCESS",
                result="success",
                created_at=NOW,
                resource_type="user",
                resource_id="iam-it-1",
                detail={},
            )
        )
    assert await store.verify() == []

    from sqlalchemy import select

    from app.modules.iam.infrastructure.models import IamAuditLogRow

    async with db_session_factory() as session:
        result = await session.execute(
            select(IamAuditLogRow).order_by(IamAuditLogRow.created_at, IamAuditLogRow.id)
        )
        rows = result.scalars().all()
    assert len(rows) == 3
    assert rows[0].prev_hash == ""
    assert rows[0].hash
    assert rows[1].prev_hash == rows[0].hash
    assert rows[2].prev_hash == rows[1].hash


async def test_cataclogo_permissions_sembrado(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.modules.iam.infrastructure.iam_security import PostgresPermissionRepository

    repo = PostgresPermissionRepository(db_session_factory)
    await repo.seed_catalog()
    permissions = await repo.list_permissions()
    assert len(permissions) > 60
    viewer = await repo.permissions_for_role(BuiltinRole.VIEWER)
    assert "server.view" in viewer
    assert "server.start" not in viewer
    operator = await repo.permissions_for_role(BuiltinRole.OPERATOR)
    assert "server.start" in operator
    assert "iam.user.create" not in operator
    admin = await repo.permissions_for_role(BuiltinRole.ADMIN)
    assert "iam.user.create" in admin


async def test_api_keys_crud(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.modules.iam.application.ports import ApiKey
    from app.modules.iam.infrastructure.iam_security import PostgresApiKeyStore

    store = PostgresApiKeyStore(db_session_factory)
    key = ApiKey(
        id="iam-key-1",
        user_id="iam-it-1",
        name="ci",
        key_hash="h" * 64,
        scopes=("server.list",),
        created_at=NOW,
    )
    await store.create(key)
    found = await store.get_by_hash("h" * 64)
    assert found is not None and found.scopes == ("server.list",)
    keys = await store.list_for_user("iam-it-1")
    assert len(keys) == 1
    await store.rotate("iam-key-1", "iam-it-1", "g" * 64)
    assert await store.get_by_hash("h" * 64) is None
    assert await store.get_by_hash("g" * 64) is not None
    await store.revoke("iam-key-1", "iam-it-1")
    assert await store.list_for_user("iam-it-1") == []


async def test_usuario_roundtrip_2fa(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresIamRepository(db_session_factory)
    user = User(
        id="iam-it-4",
        username="it-2fa",
        password_hash="x",
        display_name="2FA",
        status=UserStatus.ACTIVE,
        created_at=NOW,
        totp_secret="ciphertext",
        totp_enabled=True,
        backup_codes="cipher-codes",
    )
    await repo.save(user)
    loaded = await repo.get("iam-it-4")
    assert loaded is not None
    assert loaded.totp_secret == "ciphertext"
    assert loaded.totp_enabled is True
    assert loaded.backup_codes == "cipher-codes"


async def test_email_roundtrip(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresIamRepository(db_session_factory)
    user = User(
        id="iam-it-5",
        username="it-email",
        password_hash="x",
        display_name="Email",
        status=UserStatus.ACTIVE,
        created_at=NOW,
        email="it-email@example.com",
    )
    await repo.save(user)
    loaded = await repo.get("iam-it-5")
    assert loaded is not None and loaded.email == "it-email@example.com"


async def test_list_users_y_replace_roles(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repo = PostgresIamRepository(db_session_factory)
    await repo.save(
        User(
            id="iam-it-6",
            username="it-list-a",
            password_hash="x",
            display_name="A",
            status=UserStatus.ACTIVE,
            created_at=NOW,
        )
    )
    await repo.save(
        User(
            id="iam-it-7",
            username="it-list-b",
            password_hash="x",
            display_name="B",
            status=UserStatus.ACTIVE,
            created_at=NOW,
        )
    )
    await repo.add_global_role("iam-it-6", BuiltinRole.VIEWER)

    users = await repo.list_users()
    assert {user.username for user in users} == {"it-list-a", "it-list-b"}
    user_a = next(u for u in users if u.id == "iam-it-6")
    assert user_a.roles == {BuiltinRole.VIEWER}

    await repo.replace_global_roles(
        "iam-it-6", [BuiltinRole.ADMIN, BuiltinRole.OPERATOR]
    )
    updated = await repo.get("iam-it-6")
    assert updated is not None
    assert updated.roles == {BuiltinRole.ADMIN, BuiltinRole.OPERATOR}


async def test_audit_list_con_filtros_y_paginacion(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.modules.iam.application.ports import AuditEntry

    store = PostgresAuditStore(db_session_factory)
    for index in range(5):
        await store.record(
            AuditEntry(
                id=f"iam-lst-{index}",
                actor_id="iam-it-1",
                actor_type="user",
                action="AUTH.LOGIN_SUCCESS" if index < 3 else "IAM.USER_CREATED",
                result="success",
                created_at=NOW,
                resource_type="user",
                resource_id="iam-it-1",
                detail={"index": index},
            )
        )

    records, total = await store.list(action="login")
    assert total == 3
    assert len(records) == 3

    records, total = await store.list(actor_id="iam-it-1", limit=2, offset=0)
    assert total == 5
    assert len(records) == 2
