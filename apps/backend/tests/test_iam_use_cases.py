"""Tests de los use cases del módulo IAM (Fase C paso 8).

Usa repositorio/sesiones/auditoría en memoria y fakes de hasher/tokens; el bus
en proceso real captura los eventos publicados.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.events.event import DomainEvent
from app.kernel.ports.access import Identity
from app.modules.iam.application.commands import (
    AssignMembershipCommand,
    AssignRoleCommand,
    CreateUserCommand,
    LoginCommand,
    LogoutCommand,
    RefreshCommand,
)
from app.modules.iam.application.use_cases import (
    AssignMembershipUseCase,
    AssignRoleUseCase,
    CreateUserUseCase,
    IamDeps,
    LoginUseCase,
    LogoutUseCase,
    RefreshUseCase,
)
from app.modules.iam.domain.errors import (
    AccountSuspendedError,
    InvalidCredentialsError,
    TokenInvalidError,
    TokenRevokedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.modules.iam.domain.events import (
    AUTH_LOGIN_FAILED,
    AUTH_LOGIN_SUCCESS,
    IAM_USER_CREATED,
    IAM_USER_ROLE_CHANGED,
)
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
        if not token.startswith("temp."):
            from app.modules.iam.domain.errors import TokenInvalidError

            raise TokenInvalidError("temp token inválido")
        return token.split(".")[1]


def make_user(
    user_id: str = "u1",
    username: str = "alice",
    password: str = "pass",
    status: UserStatus = UserStatus.ACTIVE,
    roles: set[BuiltinRole] | None = None,
) -> User:
    return User(
        id=user_id,
        username=username,
        password_hash=f"hashed:{password}",
        display_name=username.title(),
        status=status,
        created_at=NOW,
        roles=set(roles or ()),
    )


class Deps:
    """Fixture de dependencias para los use cases IAM."""

    def __init__(self) -> None:
        self.repository = InMemoryIamRepository()
        self.sessions = InMemorySessionStore()
        self.audit = InMemoryAuditStore()
        self.bus = InProcessEventBus()
        self.events: list[DomainEvent] = []
        self.bus.subscribe("auth.*", self.events.append)
        self.bus.subscribe("iam.*", self.events.append)
        self.ids = SequenceIds("user-1", "user-2", "session-1", "session-2")
        self.time = FakeTime(NOW)
        self.settings = FakeSettings({})
        self.hasher = FakePasswordHasher()
        self.tokens = FakeTokenService()
        self.deps = IamDeps(
            repository=self.repository,
            sessions=self.sessions,
            audit=self.audit,
            hasher=self.hasher,
            tokens=self.tokens,
            bus=self.bus,
            ids=self.ids,
            time=self.time,
            settings=self.settings,
            permissions=InMemoryPermissionRepository(),
            api_keys=InMemoryApiKeyStore(),
            cipher=FernetSecretCipher(_FERNET_KEY),
            totp=PyotpTotpService(),
        )


def event_types(events: list[DomainEvent]) -> list[str]:
    return [e.type for e in events]


class TestCreateUser:
    async def test_crea_usuario_publica_evento_y_audita(self) -> None:
        deps = Deps()
        view = await CreateUserUseCase(deps.deps).execute(
            CreateUserCommand(
                username="bob", password="s3cret", display_name="Bob", actor_id="admin-1"
            )
        )
        assert view.username == "bob"
        assert view.status == "active"
        assert not hasattr(view, "password")
        assert event_types(deps.events) == [IAM_USER_CREATED]
        assert deps.events[0].actor_id == "admin-1"
        assert [e.action for e in deps.audit.entries] == [IAM_USER_CREATED]

    async def test_username_duplicado_rechazado(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        with pytest.raises(UserAlreadyExistsError):
            await CreateUserUseCase(deps.deps).execute(
                CreateUserCommand(username="alice", password="x", display_name="x")
            )


class TestLogin:
    async def test_login_ok_emite_tokens_y_eventos(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user(roles={BuiltinRole.VIEWER}))
        result = await LoginUseCase(deps.deps).execute(
            LoginCommand(username="alice", password="pass", ip="10.0.0.1", ua="curl")
        )
        assert result.access_token.startswith("access.u1.")
        assert result.refresh_token.startswith("refresh.")
        assert result.identity.roles == ("viewer",)
        assert event_types(deps.events) == [AUTH_LOGIN_SUCCESS]
        assert deps.events[0].actor_id == "u1"
        actions = {e.action for e in deps.audit.entries}
        assert AUTH_LOGIN_SUCCESS in actions
        stored = await deps.repository.get("u1")
        assert stored is not None and stored.last_login_at == NOW
        session = await deps.sessions.get_by_token_hash(
            deps.tokens.hash_token(result.refresh_token)
        )
        assert session is not None and session.user_id == "u1"

    async def test_login_fallido_publica_failure_y_audita(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        with pytest.raises(InvalidCredentialsError):
            await LoginUseCase(deps.deps).execute(LoginCommand(username="alice", password="wrong"))
        assert event_types(deps.events) == [AUTH_LOGIN_FAILED]
        assert [e.result for e in deps.audit.entries] == ["failure"]

    async def test_login_usuario_inexistente_mismo_error(self) -> None:
        deps = Deps()
        with pytest.raises(InvalidCredentialsError):
            await LoginUseCase(deps.deps).execute(LoginCommand(username="ghost", password="x"))

    async def test_login_cuenta_suspendida_rechazada(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user(status=UserStatus.SUSPENDED))
        with pytest.raises(AccountSuspendedError):
            await LoginUseCase(deps.deps).execute(LoginCommand(username="alice", password="pass"))
        assert AUTH_LOGIN_FAILED in event_types(deps.events)


class TestRefresh:
    async def test_rotacion_revoca_la_anterior_y_crea_nueva(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user(roles={BuiltinRole.ADMIN}))
        login = await LoginUseCase(deps.deps).execute(
            LoginCommand(username="alice", password="pass")
        )
        old_hash = deps.tokens.hash_token(login.refresh_token)

        result = await RefreshUseCase(deps.deps).execute(
            RefreshCommand(refresh_token=login.refresh_token)
        )

        assert result.access_token.startswith("access.")
        assert result.identity.roles == ("admin",)
        old = await deps.sessions.get_by_token_hash(old_hash)
        assert old is not None and old.revoked_at is not None
        new = await deps.sessions.get_by_token_hash(deps.tokens.hash_token(result.refresh_token))
        assert new is not None and new.revoked_at is None

    async def test_refresh_reutilizado_es_revocado(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        login = await LoginUseCase(deps.deps).execute(
            LoginCommand(username="alice", password="pass")
        )
        await RefreshUseCase(deps.deps).execute(RefreshCommand(refresh_token=login.refresh_token))
        with pytest.raises(TokenRevokedError):
            await RefreshUseCase(deps.deps).execute(
                RefreshCommand(refresh_token=login.refresh_token)
            )

    async def test_refresh_desconocido_invalido(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        with pytest.raises(TokenInvalidError):
            await RefreshUseCase(deps.deps).execute(RefreshCommand(refresh_token="no-existe"))


class TestLogout:
    async def test_logout_revoca_la_sesion(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        login = await LoginUseCase(deps.deps).execute(
            LoginCommand(username="alice", password="pass")
        )
        await LogoutUseCase(deps.deps).execute(LogoutCommand(refresh_token=login.refresh_token))
        session = await deps.sessions.get_by_token_hash(deps.tokens.hash_token(login.refresh_token))
        assert session is not None and session.revoked_at == NOW


class TestAssignments:
    async def test_asignar_rol_global(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        view = await AssignRoleUseCase(deps.deps).execute(
            AssignRoleCommand(user_id="u1", role=BuiltinRole.ADMIN, actor_id="admin-1")
        )
        assert view.roles == ("admin",)
        assert IAM_USER_ROLE_CHANGED in event_types(deps.events)
        assert deps.events[-1].payload["role"] == "admin"

    async def test_asignar_membresia_por_servidor(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        await AssignMembershipUseCase(deps.deps).execute(
            AssignMembershipCommand(
                user_id="u1", server_id="srv-1", role=BuiltinRole.OPERATOR, actor_id="admin-1"
            )
        )
        memberships = await deps.repository.list_memberships("u1")
        assert len(memberships) == 1
        assert memberships[0].server_id == "srv-1"
        assert memberships[0].role is BuiltinRole.OPERATOR
        assert IAM_USER_ROLE_CHANGED in event_types(deps.events)

    async def test_usuario_inexistente_en_rol(self) -> None:
        deps = Deps()
        with pytest.raises(UserNotFoundError):
            await AssignRoleUseCase(deps.deps).execute(
                AssignRoleCommand(user_id="nope", role=BuiltinRole.ADMIN)
            )
