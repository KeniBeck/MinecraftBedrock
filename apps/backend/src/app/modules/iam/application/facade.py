"""Facade pública del módulo IAM (Blueprint §3.1).

Puerta de entrada única: gestión de usuarios/roles/membresías, autenticación
(login/refresh/logout) y el ``AccessControlService`` (implementa
``AccessControlPort``) que Presentación inyectará en la Fase de APIs. No expone
entidades de dominio ni hashes.
"""

from __future__ import annotations

from datetime import datetime

from psycopg.errors import UniqueViolation

from app.kernel.ports.access import Identity
from app.modules.iam.application.access import AccessControlService
from app.modules.iam.application.commands import (
    AssignMembershipCommand,
    AssignRoleCommand,
    ConfirmTwoFactorCommand,
    CreateApiKeyCommand,
    CreateUserCommand,
    DeleteUserCommand,
    DisableTwoFactorCommand,
    EnableTwoFactorCommand,
    LoginCommand,
    LogoutCommand,
    RefreshCommand,
    RegenerateBackupCodesCommand,
    RevokeApiKeyCommand,
    RotateApiKeyCommand,
    SetAvatarCommand,
    UpdateUserCommand,
    VerifyTwoFactorLoginCommand,
)
from app.modules.iam.application.handlers import (
    BACKUP_FAILED_TOPIC,
    SERVER_CRASHED_TOPIC,
    SERVER_RESOURCES_CHANGED_TOPIC,
    TASK_FAILED_TOPIC,
    IncidentAuditHandler,
    ResourceChangeAuditHandler,
)
from app.modules.iam.application.ports import ApiKey
from app.modules.iam.application.results import (
    ApiKeyCreated,
    ApiKeyView,
    AuditLogPage,
    AuthResult,
    RoleView,
    TwoFactorEnableResult,
    UserView,
)
from app.modules.iam.application.security_use_cases import (
    ConfirmTwoFactorUseCase,
    CreateApiKeyUseCase,
    DisableTwoFactorUseCase,
    EnableTwoFactorUseCase,
    GetTwoFactorStatusUseCase,
    ListApiKeysUseCase,
    RegenerateBackupCodesUseCase,
    ResolveApiKeyUseCase,
    RevokeApiKeyUseCase,
    RotateApiKeyUseCase,
    SecurityDeps,
    VerifyTwoFactorLoginUseCase,
)
from app.modules.iam.application.use_cases import (
    AssignMembershipUseCase,
    AssignRoleUseCase,
    CreateUserUseCase,
    DeleteUserUseCase,
    GetUserUseCase,
    IamDeps,
    ListAuditLogsUseCase,
    ListRolesUseCase,
    ListUsersUseCase,
    LoginUseCase,
    LogoutUseCase,
    RefreshUseCase,
    SetAvatarUseCase,
    UpdateUserUseCase,
)
from app.modules.iam.domain.role import BuiltinRole


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
        self._list_users = ListUsersUseCase(deps)
        self._get_user = GetUserUseCase(deps)
        self._update_user = UpdateUserUseCase(deps)
        self._set_avatar = SetAvatarUseCase(deps)
        self._delete_user = DeleteUserUseCase(deps)
        self._list_roles = ListRolesUseCase(deps)
        self._list_audit_logs = ListAuditLogsUseCase(deps)
        security_deps = SecurityDeps(
            repository=deps.repository,
            sessions=deps.sessions,
            api_keys=deps.api_keys,
            tokens=deps.tokens,
            cipher=deps.cipher,
            totp=deps.totp,
            ids=deps.ids,
            time=deps.time,
            settings=deps.settings,
        )
        self._security = security_deps
        self._enable_2fa = EnableTwoFactorUseCase(security_deps)
        self._confirm_2fa = ConfirmTwoFactorUseCase(security_deps)
        self._verify_2fa_login = VerifyTwoFactorLoginUseCase(security_deps)
        self._regenerate_backup = RegenerateBackupCodesUseCase(security_deps)
        self._disable_2fa = DisableTwoFactorUseCase(security_deps)
        self._get_2fa_status = GetTwoFactorStatusUseCase(security_deps)
        self._create_api_key = CreateApiKeyUseCase(security_deps)
        self._list_api_keys = ListApiKeysUseCase(security_deps)
        self._revoke_api_key = RevokeApiKeyUseCase(security_deps)
        self._rotate_api_key = RotateApiKeyUseCase(security_deps)
        self._resolve_api_key = ResolveApiKeyUseCase(security_deps)
        self.access_control = AccessControlService(self._login, deps.repository, deps.permissions)

    # -- gestión de usuarios -----------------------------------------------

    async def create_user(self, cmd: CreateUserCommand) -> UserView:
        return await self._create_user.execute(cmd)

    async def assign_role(self, cmd: AssignRoleCommand) -> UserView:
        return await self._assign_role.execute(cmd)

    async def assign_membership(self, cmd: AssignMembershipCommand) -> None:
        await self._assign_membership.execute(cmd)

    async def list_users(self) -> list[UserView]:
        return await self._list_users.execute()

    async def get_user(self, user_id: str) -> UserView:
        return await self._get_user.execute(user_id)

    async def update_user(self, cmd: UpdateUserCommand) -> UserView:
        return await self._update_user.execute(cmd)

    async def set_avatar(self, cmd: SetAvatarCommand) -> UserView:
        return await self._set_avatar.execute(cmd)

    async def delete_user(self, cmd: DeleteUserCommand) -> None:
        await self._delete_user.execute(cmd)

    async def ensure_bootstrap_admin(
        self,
        username: str,
        password: str,
        display_name: str = "Administrador",
    ) -> str:
        """Crea (si no existe) un super_admin con las credenciales dadas.

        Bootstrap de primer arranque en producción, idempotente: si el usuario
        ya existe o ya tiene el rol super_admin, no lo duplica ni lo degrada.
        Devuelve el id del usuario (creado o existente).
        """
        deps = self.deps
        if not username or not password:
            return ""
        user = await deps.repository.get_by_username(username)
        if user is None:
            try:
                view = await self._create_user.execute(
                    CreateUserCommand(
                        username=username,
                        password=password,
                        display_name=display_name,
                        actor_id=None,
                    )
                )
                user_id = view.id
                needs_role = True
            except UniqueViolation:
                # Race con otro worker: otro proceso ya insertó el mismo username.
                # Re-resolvemos y solo aseguramos el rol (idempotente).
                user = await deps.repository.get_by_username(username)
                if user is None:
                    return ""
                user_id = user.id
                needs_role = BuiltinRole.SUPER_ADMIN not in user.roles
        else:
            user_id = user.id
            needs_role = BuiltinRole.SUPER_ADMIN not in user.roles
        if needs_role:
            await self._assign_role.execute(
                AssignRoleCommand(
                    user_id=user_id,
                    role=BuiltinRole.SUPER_ADMIN,
                    actor_id=None,
                )
            )
        return user_id

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

    # -- 2FA (Fase H paso 18) ------------------------------------------------

    async def enable_two_factor(self, cmd: EnableTwoFactorCommand) -> TwoFactorEnableResult:
        return await self._enable_2fa.execute(cmd)

    async def confirm_two_factor(self, cmd: ConfirmTwoFactorCommand) -> None:
        await self._confirm_2fa.execute(cmd)

    async def verify_two_factor_login(self, cmd: VerifyTwoFactorLoginCommand) -> AuthResult:
        return await self._verify_2fa_login.execute(cmd)

    async def regenerate_backup_codes(self, cmd: RegenerateBackupCodesCommand) -> tuple[str, ...]:
        return await self._regenerate_backup.execute(cmd)

    async def disable_two_factor(self, cmd: DisableTwoFactorCommand) -> None:
        await self._disable_2fa.execute(cmd)

    async def two_factor_status(self, user_id: str) -> bool:
        return await self._get_2fa_status.execute(user_id)

    # -- API keys (Fase H paso 18) --------------------------------------------

    async def create_api_key(self, cmd: CreateApiKeyCommand) -> ApiKeyCreated:
        return await self._create_api_key.execute(cmd)

    async def list_api_keys(self, user_id: str) -> list[ApiKeyView]:
        return await self._list_api_keys.execute(user_id)

    async def revoke_api_key(self, cmd: RevokeApiKeyCommand) -> None:
        await self._revoke_api_key.execute(cmd)

    async def rotate_api_key(self, cmd: RotateApiKeyCommand) -> ApiKeyCreated:
        return await self._rotate_api_key.execute(cmd)

    async def resolve_api_key(self, raw: str) -> ApiKey | None:
        """Devuelve la API key asociada al material (o ``None``); toca last_used."""
        return await self._resolve_api_key.resolve(raw)

    # -- auditoría tamper-evident (Fase H paso 18) -----------------------------

    async def verify_audit(self) -> list[str]:
        """Verifica la cadena de hash del audit log (vacío = íntegra)."""
        return await self.deps.audit.verify()

    async def list_audit_logs(
        self,
        *,
        actor_id: str | None = None,
        action: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AuditLogPage:
        return await self._list_audit_logs.execute(
            actor_id=actor_id,
            action=action,
            from_at=from_at,
            to_at=to_at,
            limit=limit,
            offset=offset,
        )

    async def list_roles(self) -> list[RoleView]:
        return await self._list_roles.execute()

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
        deps.bus.subscribe(
            SERVER_RESOURCES_CHANGED_TOPIC,
            ResourceChangeAuditHandler(deps.audit, deps.ids, deps.time),
        )
