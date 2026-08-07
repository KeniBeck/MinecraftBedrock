"""Facade pública del módulo IAM (Blueprint §3.1).

Puerta de entrada única: gestión de usuarios/roles/membresías, autenticación
(login/refresh/logout) y el ``AccessControlService`` (implementa
``AccessControlPort``) que Presentación inyectará en la Fase de APIs. No expone
entidades de dominio ni hashes.
"""

from __future__ import annotations

from app.kernel.ports.access import Identity
from app.modules.iam.application.access import AccessControlService
from app.modules.iam.application.commands import (
    AssignMembershipCommand,
    AssignRoleCommand,
    CreateUserCommand,
    LoginCommand,
    LogoutCommand,
    RefreshCommand,
)
from app.modules.iam.application.handlers import (
    BACKUP_FAILED_TOPIC,
    SERVER_CRASHED_TOPIC,
    TASK_FAILED_TOPIC,
    IncidentAuditHandler,
)
from app.modules.iam.application.results import AuthResult, UserView
from app.modules.iam.application.use_cases import (
    AssignMembershipUseCase,
    AssignRoleUseCase,
    CreateUserUseCase,
    IamDeps,
    LoginUseCase,
    LogoutUseCase,
    RefreshUseCase,
)


class IamFacade:
    """Puerta de entrada única al módulo IAM."""

    def __init__(self, deps: IamDeps) -> None:
        self.deps = deps
        self._create_user = CreateUserUseCase(deps)
        self._login = LoginUseCase(deps)
        self._refresh = RefreshUseCase(deps)
        self._logout = LogoutUseCase(deps)
        self._assign_role = AssignRoleUseCase(deps)
        self._assign_membership = AssignMembershipUseCase(deps)
        self.access_control = AccessControlService(self._login, deps.repository)

    # -- gestión de usuarios -----------------------------------------------

    async def create_user(self, cmd: CreateUserCommand) -> UserView:
        return await self._create_user.execute(cmd)

    async def assign_role(self, cmd: AssignRoleCommand) -> UserView:
        return await self._assign_role.execute(cmd)

    async def assign_membership(self, cmd: AssignMembershipCommand) -> None:
        await self._assign_membership.execute(cmd)

    # -- autenticación ------------------------------------------------------

    async def login(self, cmd: LoginCommand) -> AuthResult:
        return await self._login.execute(cmd)

    async def refresh(self, cmd: RefreshCommand) -> AuthResult:
        return await self._refresh.execute(cmd)

    async def logout(self, cmd: LogoutCommand) -> None:
        await self._logout.execute(cmd)

    def resolve_access(self, token: str) -> Identity:
        """Decodifica y valida un access token Bearer (presentación).

        Es el punto de entrada de ``get_current_user``; la autenticación por
        credenciales sigue usando ``AccessControlPort.authenticate``.
        """
        claims = self.deps.tokens.decode_access_token(token)
        return Identity(
            id=str(claims["sub"]),
            username=str(claims.get("username", "")),
            roles=tuple(str(role) for role in claims.get("roles", [])),
        )

    # -- eventos consumidos --------------------------------------------------

    def register_handlers(self) -> None:
        """Suscriptores del módulo sobre el bus (Blueprint §3.1)."""
        deps = self.deps
        deps.bus.subscribe(
            SERVER_CRASHED_TOPIC,
            IncidentAuditHandler(deps.audit, deps.ids, deps.time, "server.crashed", "server"),
        )
        deps.bus.subscribe(
            TASK_FAILED_TOPIC,
            IncidentAuditHandler(deps.audit, deps.ids, deps.time, "task.failed", "task"),
        )
        deps.bus.subscribe(
            BACKUP_FAILED_TOPIC,
            IncidentAuditHandler(deps.audit, deps.ids, deps.time, "backup.failed", "backup"),
        )
