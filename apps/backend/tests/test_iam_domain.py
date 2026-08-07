"""Tests del dominio IAM (rol, jerarquía, estado de usuario, errores)."""

from __future__ import annotations

import pytest

from app.kernel.errors import AppError
from app.modules.iam.domain.errors import (
    AccountSuspendedError,
    ForbiddenError,
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    TokenRevokedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.modules.iam.domain.role import ROLE_LEVEL, BuiltinRole, ServerMembership
from app.modules.iam.domain.user import UserStatus


class TestBuiltinRoles:
    def test_roles_base_son_los_cuatro_definidos(self) -> None:
        assert {r.value for r in BuiltinRole} == {
            "super_admin",
            "admin",
            "operator",
            "viewer",
        }

    def test_jerarquia_strictamente_descendente(self) -> None:
        levels = [ROLE_LEVEL[r] for r in BuiltinRole]
        assert levels == sorted(levels, reverse=True)
        assert ROLE_LEVEL[BuiltinRole.SUPER_ADMIN] > ROLE_LEVEL[BuiltinRole.ADMIN]
        assert ROLE_LEVEL[BuiltinRole.ADMIN] > ROLE_LEVEL[BuiltinRole.OPERATOR]
        assert ROLE_LEVEL[BuiltinRole.OPERATOR] > ROLE_LEVEL[BuiltinRole.VIEWER]


class TestUserStatus:
    def test_estados_validos(self) -> None:
        assert UserStatus.ACTIVE.value == "active"
        assert UserStatus.SUSPENDED.value == "suspended"


class TestServerMembership:
    def test_membresia_congela_servidor_usuario_y_rol(self) -> None:
        membership = ServerMembership("srv-1", "user-1", BuiltinRole.OPERATOR)
        assert membership.server_id == "srv-1"
        assert membership.user_id == "user-1"
        assert membership.role is BuiltinRole.OPERATOR


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (UserNotFoundError, "IAM.USER_NOT_FOUND"),
        (UserAlreadyExistsError, "IAM.USER_ALREADY_EXISTS"),
        (InvalidCredentialsError, "AUTH.INVALID_CREDENTIALS"),
        (AccountSuspendedError, "AUTH.ACCOUNT_SUSPENDED"),
        (TokenInvalidError, "AUTH.TOKEN_INVALID"),
        (TokenExpiredError, "AUTH.TOKEN_EXPIRED"),
        (TokenRevokedError, "AUTH.TOKEN_REVOKED"),
        (ForbiddenError, "AUTH.FORBIDDEN"),
    ],
)
def test_codigos_de_error(error: type[AppError], code: str) -> None:
    assert error("boom").code == code
