"""Tests de la matriz de permisos por acción (Fase H paso 18, TDD §14.2).

Tabla de casos: rol de membresía × acción (lectura/escritura/panel) × ámbito.
50+ combinaciones parametrizadas sobre la matriz ``ROLE_PERMISSIONS``.
"""

from __future__ import annotations

import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.ports.access import AuthorizationDecision, Identity
from app.modules.iam.application.access import AccessControlService
from app.modules.iam.application.use_cases import IamDeps, LoginUseCase
from app.modules.iam.domain.permissions import (
    ALL_PERMISSIONS,
    PANEL_ACTIONS,
    PERMISSIONS_SEED,
    READ_ACTIONS,
    ROLE_PERMISSIONS,
    WRITE_ACTIONS,
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
from tests.test_iam_use_cases import NOW, FakePasswordHasher, FakeTokenService

SRV = "srv-1"
_FERNET_KEY = "9Dfa2Y5t4kMX6k4oyar_EgtQ1cFcdPE8V_6I688Tu4k="

SERVER_READ = "server.view"
SERVER_WRITE = "server.start"
BACKUP_WRITE = "backup.restore"
PANEL_ACTION = "iam.user.create"


class TestCatalog:
    def test_catalogo_organizado_por_categorias(self) -> None:
        categories = {p.category for p in PERMISSIONS_SEED}
        assert {"server", "world", "backup", "player", "iam", "settings"} <= categories
        codes = {p.code for p in PERMISSIONS_SEED}
        assert codes == ALL_PERMISSIONS

    def test_lectura_escritura_y_panel_disjuntos(self) -> None:
        assert not (READ_ACTIONS & WRITE_ACTIONS)
        assert not (READ_ACTIONS & PANEL_ACTIONS)
        assert not (WRITE_ACTIONS & PANEL_ACTIONS)
        assert READ_ACTIONS | WRITE_ACTIONS | PANEL_ACTIONS == ALL_PERMISSIONS

    def test_viewer_solo_lectura(self) -> None:
        viewer = ROLE_PERMISSIONS[BuiltinRole.VIEWER]
        assert viewer == READ_ACTIONS
        assert SERVER_WRITE not in viewer

    def test_operator_lectura_mas_escritura(self) -> None:
        operator = ROLE_PERMISSIONS[BuiltinRole.OPERATOR]
        assert operator == READ_ACTIONS | WRITE_ACTIONS
        assert not (operator & PANEL_ACTIONS)

    def test_admin_y_super_admin_todo(self) -> None:
        assert ROLE_PERMISSIONS[BuiltinRole.ADMIN] == ALL_PERMISSIONS
        assert ROLE_PERMISSIONS[BuiltinRole.SUPER_ADMIN] == ALL_PERMISSIONS


class TestMatrixCombinaciones:
    @pytest.mark.parametrize(
        ("role", "action"),
        [(BuiltinRole.VIEWER, action) for action in sorted(READ_ACTIONS)]
        + [(BuiltinRole.VIEWER, action) for action in sorted(WRITE_ACTIONS | PANEL_ACTIONS)]
        + [(BuiltinRole.OPERATOR, action) for action in sorted(READ_ACTIONS | WRITE_ACTIONS)]
        + [(BuiltinRole.OPERATOR, action) for action in sorted(PANEL_ACTIONS)]
        + [(BuiltinRole.ADMIN, action) for action in sorted(ALL_PERMISSIONS)],
    )
    async def test_membresia_concede_segun_matriz(self, role: BuiltinRole, action: str) -> None:
        expected = action in ROLE_PERMISSIONS[role]
        decision = await self._authorize(role, action)
        assert decision.allowed is expected, f"{role.value}/{action} → {expected}"

    async def _authorize(self, role: BuiltinRole, action: str) -> AuthorizationDecision:
        service = await self._build(role)
        return await service.authorize(identity(role), action, SRV)

    @staticmethod
    async def _build(role: BuiltinRole) -> AccessControlService:
        repository = InMemoryIamRepository()
        user = User(
            id="u1",
            username="alice",
            password_hash="hashed:pass",
            display_name="Alice",
            status=UserStatus.ACTIVE,
            created_at=NOW,
        )
        await repository.save(user)
        await repository.add_membership("u1", SRV, role)
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
        return AccessControlService(LoginUseCase(deps), repository, deps.permissions)


def identity(role: BuiltinRole) -> Identity:
    return Identity(id="u1", username="alice", roles=(role.value,))
