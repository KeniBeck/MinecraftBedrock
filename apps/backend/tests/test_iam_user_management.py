"""Tests de los use cases de gestión de usuarios, roles y auditoría (Fase 8).

Cubre ``ListUsers``, ``GetUser``, ``UpdateUser``, ``DeleteUser`` (soft delete),
``ListRoles`` y ``ListAuditLogs`` con repositorio/sesiones/auditoría en memoria
(mismo arnés que ``test_iam_use_cases.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.ports.access import Identity
from app.modules.iam.application.commands import (
    DeleteUserCommand,
    UpdateUserCommand,
)
from app.modules.iam.application.ports import AuditEntry
from app.modules.iam.application.use_cases import (
    DeleteUserUseCase,
    GetUserUseCase,
    IamDeps,
    ListAuditLogsUseCase,
    ListRolesUseCase,
    ListUsersUseCase,
    UpdateUserUseCase,
)
from app.modules.iam.domain.errors import UserNotFoundError
from app.modules.iam.domain.events import IAM_USER_SUSPENDED
from app.modules.iam.domain.role import BuiltinRole
from app.modules.iam.domain.user import User, UserStatus
from app.modules.iam.infrastructure.iam_security import (
    FernetSecretCipher,
    PyotpTotpService,
)
from app.modules.iam.infrastructure.memory import (
    InMemoryApiKeyStore,
    InMemoryAuditStore,
    InMemoryIamRepository,
    InMemoryPermissionRepository,
    InMemorySessionStore,
)
from tests.conftest import FakeSettings, FakeTime, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)

_FERNET_KEY = "9Dfa2Y5t4kMX6k4oyar_EgtQ1cFcdPE8V_6I688Tu4k="


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed:{password}"


def make_user(
    user_id: str,
    username: str,
    email: str | None = None,
    roles: set[BuiltinRole] | None = None,
) -> User:
    return User(
        id=user_id,
        username=username,
        password_hash="hashed:pass",
        display_name=username.title(),
        status=UserStatus.ACTIVE,
        created_at=NOW,
        email=email,
        roles=set(roles or ()),
    )


class Deps:
    """Dependencias en memoria para los use cases de gestión IAM."""

    def __init__(self) -> None:
        self.repository = InMemoryIamRepository()
        self.sessions = InMemorySessionStore()
        self.audit = InMemoryAuditStore()
        self.bus = InProcessEventBus()
        self.ids = SequenceIds("user-1", "user-2", "session-1", "session-2")
        self.time = FakeTime(NOW)
        self.settings = FakeSettings({})
        self.deps = IamDeps(
            repository=self.repository,
            sessions=self.sessions,
            audit=self.audit,
            hasher=FakePasswordHasher(),
            tokens=FakeTokenService(),
            bus=self.bus,
            ids=self.ids,
            time=self.time,
            settings=self.settings,
            permissions=InMemoryPermissionRepository(),
            api_keys=InMemoryApiKeyStore(),
            cipher=FernetSecretCipher(_FERNET_KEY),
            totp=PyotpTotpService(),
        )


class FakeTokenService:
    def __init__(self) -> None:
        self._n = 0

    def create_access_token(self, identity: Identity) -> str:
        token = f"access.{identity.id}.{self._n}"
        self._n += 1
        return token

    def decode_access_token(self, token: str) -> dict[str, Any]:
        del token
        return {}

    def generate_refresh_token(self) -> str:
        token = f"refresh.{self._n}"
        self._n += 1
        return token

    def hash_token(self, raw: str) -> str:
        return f"sha256:{raw}"

    def create_temp_token(self, user_id: str) -> str:
        token = f"temp.{user_id}.{self._n}"
        self._n += 1
        return token

    def decode_temp_token(self, token: str) -> str:
        del token
        return "u1"


class TestListUsers:
    async def test_lista_usuarios_con_roles_y_email(self) -> None:
        deps = Deps()
        await deps.repository.save(
            make_user("u1", "alice", email="alice@example.com", roles={BuiltinRole.VIEWER})
        )
        await deps.repository.save(make_user("u2", "bob", roles={BuiltinRole.ADMIN}))

        views = await ListUsersUseCase(deps.deps).execute()

        assert len(views) == 2
        by_id = {view.id: view for view in views}
        assert by_id["u1"].email == "alice@example.com"
        assert by_id["u1"].roles == ("viewer",)
        assert by_id["u2"].roles == ("admin",)


class TestGetUser:
    async def test_detalle_existente(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user("u1", "alice", email="a@example.com"))
        view = await GetUserUseCase(deps.deps).execute("u1")
        assert view.username == "alice"
        assert view.email == "a@example.com"

    async def test_usuario_inexistente(self) -> None:
        deps = Deps()
        with pytest.raises(UserNotFoundError):
            await GetUserUseCase(deps.deps).execute("no-existe")


class TestUpdateUser:
    async def test_actualiza_campos_parciales(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user("u1", "alice", roles={BuiltinRole.VIEWER}))

        view = await UpdateUserUseCase(deps.deps).execute(
            UpdateUserCommand(
                user_id="u1",
                display_name="Alice Updated",
                email="new@example.com",
                status="suspended",
                roles=(BuiltinRole.ADMIN,),
                actor_id="admin-1",
            )
        )

        assert view.display_name == "Alice Updated"
        assert view.email == "new@example.com"
        assert view.status == "suspended"
        assert view.roles == ("admin",)

        stored = await deps.repository.get("u1")
        assert stored is not None
        assert stored.email == "new@example.com"
        assert stored.status is UserStatus.SUSPENDED
        assert stored.roles == {BuiltinRole.ADMIN}

    async def test_sin_roles_no_reemplaza(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user("u1", "alice", roles={BuiltinRole.OPERATOR}))

        view = await UpdateUserUseCase(deps.deps).execute(
            UpdateUserCommand(user_id="u1", display_name="Otro", actor_id="admin-1")
        )

        assert view.roles == ("operator",)

    async def test_inexistente(self) -> None:
        deps = Deps()
        with pytest.raises(UserNotFoundError):
            await UpdateUserUseCase(deps.deps).execute(
                UpdateUserCommand(user_id="no", display_name="x")
            )


class TestDeleteUser:
    async def test_suspende_y_audita(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user("u1", "alice"))

        await DeleteUserUseCase(deps.deps).execute(
            DeleteUserCommand(user_id="u1", actor_id="admin-1")
        )

        stored = await deps.repository.get("u1")
        assert stored is not None and stored.status is UserStatus.SUSPENDED
        assert [e.action for e in deps.audit.entries] == [IAM_USER_SUSPENDED]

    async def test_inexistente(self) -> None:
        deps = Deps()
        with pytest.raises(UserNotFoundError):
            await DeleteUserUseCase(deps.deps).execute(
                DeleteUserCommand(user_id="no", actor_id="admin-1")
            )


class TestListRoles:
    async def test_catalogo_base(self) -> None:
        deps = Deps()
        views = await ListRolesUseCase(deps.deps).execute()
        names = {view.name for view in views}
        assert names == {role.value for role in BuiltinRole}
        assert all(view.is_system for view in views)
        assert all(view.id == view.name for view in views)


class TestListAuditLogs:
    async def test_lista_con_filtros_y_paginacion(self) -> None:
        deps = Deps()
        for index in range(3):
            await deps.audit.record(
                AuditEntry(
                    id=f"aud-{index}",
                    actor_id="u1" if index % 2 == 0 else "u2",
                    actor_type="user",
                    action="AUTH.LOGIN_SUCCESS" if index < 2 else "IAM.USER_CREATED",
                    result="success",
                    created_at=NOW,
                    resource_type="user",
                    resource_id="u1",
                    detail={},
                )
            )

        page = await ListAuditLogsUseCase(deps.deps).execute(action="login")
        assert page.total == 2
        assert all("login" in item.action.lower() for item in page.items)

        page_u1 = await ListAuditLogsUseCase(deps.deps).execute(actor_id="u1")
        assert page_u1.total == 2

        limited = await ListAuditLogsUseCase(deps.deps).execute(limit=1, offset=0)
        assert len(limited.items) == 1
        assert limited.total == 3

    async def test_filtro_vacio_devuelve_vacio(self) -> None:
        deps = Deps()
        page = await ListAuditLogsUseCase(deps.deps).execute(actor_id="nadie")
        assert page.items == []
        assert page.total == 0