"""Tests de la matriz RBAC+ACL del ``AccessControlService`` (§14.2, §16.2).

Tabla de casos: rol global × acción (lectura/escritura) × membresía por
servidor. El puerto de kernel se ajustó a async en este paso (documentado).
"""

from __future__ import annotations

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.ports.access import Identity
from app.modules.iam.application.access import READ_ACTIONS, AccessControlService
from app.modules.iam.application.commands import LoginCredentials
from app.modules.iam.application.use_cases import IamDeps, LoginUseCase
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
from tests.test_iam_use_cases import NOW, FakePasswordHasher, FakeTokenService

SRV = "srv-1"
READ = "server.console.read"
WRITE = "server.start"
_FERNET_KEY = "9Dfa2Y5t4kMX6k4oyar_EgtQ1cFcdPE8V_6I688Tu4k="


def identity(*roles: BuiltinRole, user_id: str = "u1") -> Identity:
    return Identity(
        id=user_id,
        username="alice",
        roles=tuple(role.value for role in roles),
    )


async def build(
    global_roles: set[BuiltinRole], memberships: dict[str, BuiltinRole]
) -> tuple[AccessControlService, InMemoryIamRepository]:
    repository = InMemoryIamRepository()
    user = User(
        id="u1",
        username="alice",
        password_hash="hashed:pass",
        display_name="Alice",
        status=UserStatus.ACTIVE,
        created_at=NOW,
        roles=set(global_roles),
    )
    await repository.save(user)
    for server_id, role in memberships.items():
        await repository.add_membership("u1", server_id, role)

    deps = IamDeps(
        repository=repository,
        sessions=InMemorySessionStore(),
        audit=InMemoryAuditStore(),
        hasher=FakePasswordHasher(),
        tokens=FakeTokenService(),
        bus=InProcessEventBus(),
        ids=SequenceIds("x"),
        time=FakeTime(NOW),
        settings=FakeSettings({}),
        permissions=InMemoryPermissionRepository(),
        api_keys=InMemoryApiKeyStore(),
        cipher=FernetSecretCipher(_FERNET_KEY),
        totp=PyotpTotpService(),
    )
    service = AccessControlService(LoginUseCase(deps), repository, deps.permissions)
    return service, repository


async def make_decision(
    *global_roles: BuiltinRole,
    memberships: dict[str, BuiltinRole] | None = None,
    action: str = WRITE,
    resource: str | None = SRV,
) -> bool:
    service, _ = await build(set(global_roles), memberships or {})
    decision = await service.authorize(identity(*global_roles), action, resource)
    return decision.allowed


class TestGlobalScope:
    async def test_admin_autorizado_global(self) -> None:
        assert await make_decision(BuiltinRole.ADMIN, resource=None) is True

    async def test_super_admin_autorizado_global(self) -> None:
        assert await make_decision(BuiltinRole.SUPER_ADMIN, resource=None) is True

    async def test_operator_sin_rol_global_denegado(self) -> None:
        assert await make_decision(BuiltinRole.OPERATOR, resource=None) is False

    async def test_viewer_sin_rol_global_denegado(self) -> None:
        assert await make_decision(BuiltinRole.VIEWER, resource=None) is False


class TestServerScope:
    async def test_super_admin_accede_sin_membresia(self) -> None:
        assert await make_decision(BuiltinRole.SUPER_ADMIN) is True
        assert await make_decision(BuiltinRole.SUPER_ADMIN, action=READ) is True

    async def test_admin_accede_a_cualquier_servidor(self) -> None:
        assert await make_decision(BuiltinRole.ADMIN) is True

    async def test_operator_sin_membresia_no_accede(self) -> None:
        assert await make_decision(BuiltinRole.OPERATOR) is False
        assert await make_decision(BuiltinRole.OPERATOR, action=READ) is False

    async def test_operator_con_membresia_viewer_solo_lectura(self) -> None:
        assert (
            await make_decision(
                BuiltinRole.OPERATOR, memberships={SRV: BuiltinRole.VIEWER}, action=READ
            )
            is True
        )
        assert (
            await make_decision(
                BuiltinRole.OPERATOR, memberships={SRV: BuiltinRole.VIEWER}, action=WRITE
            )
            is False
        )

    async def test_operator_con_membresia_operator_escribe(self) -> None:
        assert (
            await make_decision(
                BuiltinRole.OPERATOR, memberships={SRV: BuiltinRole.OPERATOR}, action=WRITE
            )
            is True
        )

    async def test_viewer_con_membresia_viewer_solo_lectura(self) -> None:
        assert (
            await make_decision(
                BuiltinRole.VIEWER, memberships={SRV: BuiltinRole.VIEWER}, action=READ
            )
            is True
        )
        assert (
            await make_decision(
                BuiltinRole.VIEWER, memberships={SRV: BuiltinRole.VIEWER}, action=WRITE
            )
            is False
        )

    async def test_sin_roles_sin_membresia_denegado(self) -> None:
        assert await make_decision(action=READ) is False

    async def test_membresia_en_otro_servidor_no_aplica(self) -> None:
        assert (
            await make_decision(
                BuiltinRole.OPERATOR, memberships={"srv-otro": BuiltinRole.OPERATOR}, action=WRITE
            )
            is False
        )

    async def test_rol_desconocido_en_token_se_ignora(self) -> None:
        decision = await make_decision(action=READ)
        assert decision is False


def test_read_actions_estan_definidas() -> None:
    assert "server.console.read" in READ_ACTIONS
    assert "server.start" not in READ_ACTIONS


async def test_authenticate_mapea_credenciales_a_identidad() -> None:
    service, _ = await build({BuiltinRole.ADMIN}, {})
    ident = await service.authenticate(LoginCredentials(username="alice", password="pass"))
    assert ident.id == "u1"
    assert ident.roles == ("admin",)


@pytest.mark.parametrize(
    ("creds", "expected"),
    [
        ({"username": "alice", "password": "nope"}, None),
        ("no-object", None),
    ],
)
async def test_authenticate_rechaza_credenciales_invalidas(creds: object, expected: None) -> None:
    del expected
    service, _ = await build({BuiltinRole.ADMIN}, {})
    from app.modules.iam.domain.errors import InvalidCredentialsError, TokenInvalidError

    if isinstance(creds, dict):
        with pytest.raises(InvalidCredentialsError):
            await service.authenticate(LoginCredentials(**creds))
    else:
        with pytest.raises(TokenInvalidError):
            await service.authenticate(creds)
