"""Use cases del módulo IAM (Blueprint §3.1, §16.2 — mínimo viable).

Cada use case recibe sus puertos vía ``IamDeps``; nunca importa infraestructura.
Flujos: crear usuario, login, refresh rotativo, logout/revocación, asignar rol
global y asignar membresía por servidor. Los eventos ``AUTH.*``/``IAM.*`` se
publican solo vía ``EventBusPort`` y las operaciones sensibles se auditan (log
básico).

La autorización del actor (¿quién puede crear usuarios/roles?) es
responsabilidad de Presentación vía ``AccessControlPort`` (fuera de este paso);
los use cases registran ``actor_id`` sin comprobar permisos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.kernel.events.bus import EventBusPort
from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.access import Identity
from app.kernel.ports.settings import SettingsPort
from app.kernel.time import TimeProviderPort
from app.modules.iam.application.commands import (
    AssignMembershipCommand,
    AssignRoleCommand,
    CreateUserCommand,
    DeleteUserCommand,
    LoginCommand,
    LogoutCommand,
    RefreshCommand,
    SetAvatarCommand,
    UpdateUserCommand,
)
from app.modules.iam.application.ports import (
    ApiKeyStorePort,
    AuditEntry,
    AuditStorePort,
    PasswordHasher,
    SecretCipherPort,
    Session,
    SessionStorePort,
    TokenService,
    TotpServicePort,
)
from app.modules.iam.application.results import (
    AuditLogPage,
    AuditLogView,
    AuthResult,
    RoleView,
    UserView,
)
from app.modules.iam.domain.errors import (
    AccountSuspendedError,
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    TokenRevokedError,
    TwoFactorRequiredError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.modules.iam.domain.events import (
    AUTH_LOGIN_FAILED,
    AUTH_LOGIN_SUCCESS,
    IAM_USER_CREATED,
    IAM_USER_REACTIVATED,
    IAM_USER_ROLE_CHANGED,
    IAM_USER_SUSPENDED,
    IAM_USER_UPDATED,
    iam_event,
)
from app.modules.iam.domain.repository import IamRepositoryPort, PermissionRepositoryPort
from app.modules.iam.domain.role import BuiltinRole
from app.modules.iam.domain.user import User, UserStatus


@dataclass(slots=True)
class IamDeps:
    """Dependencias comunes de los use cases del módulo IAM."""

    repository: IamRepositoryPort
    sessions: SessionStorePort
    audit: AuditStorePort
    hasher: PasswordHasher
    tokens: TokenService
    bus: EventBusPort
    ids: IdGeneratorPort
    time: TimeProviderPort
    settings: SettingsPort
    permissions: PermissionRepositoryPort
    api_keys: ApiKeyStorePort
    cipher: SecretCipherPort
    totp: TotpServicePort


def to_identity(user: User) -> Identity:
    return Identity(
        id=user.id,
        username=user.username,
        roles=tuple(sorted(role.value for role in user.roles)),
    )


def to_view(user: User) -> UserView:
    return UserView(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=user.status.value,
        roles=tuple(sorted(role.value for role in user.roles)),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        email=user.email,
        avatar=user.avatar,
    )


class CreateUserUseCase:
    """Admin crea un usuario (Bluepring §16.2)."""

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: CreateUserCommand) -> UserView:
        deps = self._deps
        if await deps.repository.get_by_username(cmd.username) is not None:
            raise UserAlreadyExistsError(
                f"Username ya en uso: {cmd.username}",
                context={"username": cmd.username},
            )

        now = deps.time.now()
        user = User(
            id=deps.ids.new_id(),
            username=cmd.username,
            password_hash=deps.hasher.hash(cmd.password),
            display_name=cmd.display_name or cmd.username,
            status=UserStatus.ACTIVE,
            created_at=now,
        )
        await deps.repository.save(user)
        await deps.bus.publish(
            iam_event(
                IAM_USER_CREATED,
                actor_id=cmd.actor_id,
                payload={"user_id": user.id, "username": user.username},
            )
        )
        await deps.audit.record(
            AuditEntry(
                id=deps.ids.new_id(),
                actor_id=cmd.actor_id,
                actor_type="user",
                action=IAM_USER_CREATED,
                result="success",
                created_at=now,
                resource_type="user",
                resource_id=user.id,
                detail={"username": user.username},
            )
        )
        return to_view(user)


class LoginUseCase:
    """Login con credenciales: valida, crea sesión y emite tokens (§14.1)."""

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: LoginCommand) -> AuthResult:
        deps = self._deps
        now = deps.time.now()
        user = await deps.repository.get_by_username(cmd.username)

        if user is None or not deps.hasher.verify(cmd.password, user.password_hash):
            await self._record_failure(user.id if user else None, cmd)
            raise InvalidCredentialsError("Credenciales inválidas")

        if user.status is not UserStatus.ACTIVE:
            await self._record_failure(user.id, cmd)
            raise AccountSuspendedError(
                f"Cuenta suspendida: {user.username}",
                context={"username": user.username},
            )

        if user.totp_enabled:
            temp_token = deps.tokens.create_temp_token(user.id)
            raise TwoFactorRequiredError(
                "La cuenta exige el segundo factor",
                context={"temp_token": temp_token},
            )

        identity = to_identity(user)
        refresh_raw = deps.tokens.generate_refresh_token()
        await deps.sessions.create(
            Session(
                id=deps.ids.new_id(),
                user_id=user.id,
                token_hash=deps.tokens.hash_token(refresh_raw),
                expires_at=now + self._refresh_ttl(),
                created_at=now,
                ip=cmd.ip,
                ua=cmd.ua,
            )
        )
        await deps.repository.touch_last_login(user.id, now)
        await deps.bus.publish(
            iam_event(AUTH_LOGIN_SUCCESS, actor_id=user.id, payload={"user_id": user.id})
        )
        await deps.audit.record(
            AuditEntry(
                id=deps.ids.new_id(),
                actor_id=user.id,
                actor_type="user",
                action=AUTH_LOGIN_SUCCESS,
                result="success",
                created_at=now,
                resource_type="user",
                resource_id=user.id,
                ip=cmd.ip,
                ua=cmd.ua,
            )
        )
        return AuthResult(
            access_token=deps.tokens.create_access_token(identity),
            refresh_token=refresh_raw,
            expires_in=self._access_ttl(),
            identity=identity,
        )

    def _refresh_ttl(self) -> timedelta:
        seconds = int(self._deps.settings.get("iam.refresh_token_ttl_seconds", 2592000))
        return timedelta(seconds=seconds)

    def _access_ttl(self) -> int:
        return int(self._deps.settings.get("iam.access_token_ttl_seconds", 900))

    async def _record_failure(self, actor_id: str | None, cmd: LoginCommand) -> None:
        deps = self._deps
        await deps.bus.publish(
            iam_event(
                AUTH_LOGIN_FAILED,
                actor_id=actor_id,
                payload={"username": cmd.username},
            )
        )
        await deps.audit.record(
            AuditEntry(
                id=deps.ids.new_id(),
                actor_id=actor_id,
                actor_type="user",
                action=AUTH_LOGIN_FAILED,
                result="failure",
                created_at=deps.time.now(),
                resource_type="user",
                detail={"username": cmd.username},
                ip=cmd.ip,
                ua=cmd.ua,
            )
        )


class RefreshUseCase:
    """Refresh rotativo: valida, revoca la sesión y emite tokens nuevos (§14.1)."""

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: RefreshCommand) -> AuthResult:
        deps = self._deps
        now = deps.time.now()
        token_hash = deps.tokens.hash_token(cmd.refresh_token)
        session = await deps.sessions.get_by_token_hash(token_hash)
        if session is None:
            raise TokenInvalidError("Refresh token inválido")
        if session.revoked_at is not None:
            raise TokenRevokedError("Refresh token ya revocado")
        if session.expires_at <= now:
            raise TokenExpiredError("Refresh token vencido")

        user = await deps.repository.get(session.user_id)
        if user is None:
            raise UserNotFoundError(
                f"Usuario de la sesión no encontrado: {session.user_id}",
                context={"user_id": session.user_id},
            )
        if user.status is not UserStatus.ACTIVE:
            raise AccountSuspendedError(
                f"Cuenta suspendida: {user.username}",
                context={"username": user.username},
            )

        await deps.sessions.revoke(session.id, now)
        refresh_raw = deps.tokens.generate_refresh_token()
        await deps.sessions.create(
            Session(
                id=deps.ids.new_id(),
                user_id=user.id,
                token_hash=deps.tokens.hash_token(refresh_raw),
                expires_at=session.expires_at,
                created_at=now,
                ip=cmd.ip,
                ua=cmd.ua,
            )
        )

        identity = to_identity(user)
        return AuthResult(
            access_token=deps.tokens.create_access_token(identity),
            refresh_token=refresh_raw,
            expires_in=int(deps.settings.get("iam.access_token_ttl_seconds", 900)),
            identity=identity,
        )


class LogoutUseCase:
    """Logout/revocación: inutiliza la sesión de refresh."""

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: LogoutCommand) -> None:
        deps = self._deps
        token_hash = deps.tokens.hash_token(cmd.refresh_token)
        session = await deps.sessions.get_by_token_hash(token_hash)
        if session is None:
            raise TokenInvalidError("Refresh token inválido")
        await deps.sessions.revoke(session.id, deps.time.now())


class AssignRoleUseCase:
    """Admin concede un rol global a un usuario (§14.2 RBAC)."""

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: AssignRoleCommand) -> UserView:
        deps = self._deps
        user = await self._require_user(cmd.user_id)
        user.roles.add(cmd.role)
        await deps.repository.add_global_role(cmd.user_id, cmd.role)
        await deps.bus.publish(
            iam_event(
                IAM_USER_ROLE_CHANGED,
                actor_id=cmd.actor_id,
                payload={"user_id": user.id, "role": cmd.role.value},
            )
        )
        await deps.audit.record(
            AuditEntry(
                id=deps.ids.new_id(),
                actor_id=cmd.actor_id,
                actor_type="user",
                action=IAM_USER_ROLE_CHANGED,
                result="success",
                created_at=deps.time.now(),
                resource_type="user",
                resource_id=user.id,
                detail={"role": cmd.role.value, "scope": "global"},
            )
        )
        return to_view(user)

    async def _require_user(self, user_id: str) -> User:
        user = await self._deps.repository.get(user_id)
        if user is None:
            raise UserNotFoundError(
                f"Usuario no encontrado: {user_id}",
                context={"user_id": user_id},
            )
        return user


class AssignMembershipUseCase:
    """Admin concede/actualiza la membresía de un usuario sobre un servidor (§14.2 ACL)."""

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: AssignMembershipCommand) -> None:
        deps = self._deps
        user = await deps.repository.get(cmd.user_id)
        if user is None:
            raise UserNotFoundError(
                f"Usuario no encontrado: {cmd.user_id}",
                context={"user_id": cmd.user_id},
            )
        await deps.repository.add_membership(cmd.user_id, cmd.server_id, cmd.role)
        await deps.bus.publish(
            iam_event(
                IAM_USER_ROLE_CHANGED,
                actor_id=cmd.actor_id,
                payload={
                    "user_id": user.id,
                    "server_id": cmd.server_id,
                    "role": cmd.role.value,
                },
            )
        )
        await deps.audit.record(
            AuditEntry(
                id=deps.ids.new_id(),
                actor_id=cmd.actor_id,
                actor_type="user",
                action=IAM_USER_ROLE_CHANGED,
                result="success",
                created_at=deps.time.now(),
                resource_type="server",
                resource_id=cmd.server_id,
                detail={"user_id": user.id, "role": cmd.role.value, "scope": "server"},
            )
        )


class ListUsersUseCase:
    """Admin consulta el listado de usuarios (get: ``iam.view``)."""

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self) -> list[UserView]:
        users = await self._deps.repository.list_users()
        return [to_view(user) for user in users]


class GetUserUseCase:
    """Devuelve el detalle de un usuario (get: ``iam.view``)."""

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self, user_id: str) -> UserView:
        user = await self._deps.repository.get(user_id)
        if user is None:
            raise UserNotFoundError(
                f"Usuario no encontrado: {user_id}",
                context={"user_id": user_id},
            )
        return to_view(user)


class UpdateUserUseCase:
    """Admin actualiza campos parciales de un usuario (get: ``iam.manage``).

    ``username`` y ``password`` son inmutables aquí (el primero es la clave
    natural; el segundo se gestiona por endpoint de contraseña). ``roles``, si
    se indica, reemplaza el conjunto de roles globales del usuario.
    """

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: UpdateUserCommand) -> UserView:
        deps = self._deps
        user = await deps.repository.get(cmd.user_id)
        if user is None:
            raise UserNotFoundError(
                f"Usuario no encontrado: {cmd.user_id}",
                context={"user_id": cmd.user_id},
            )

        if cmd.display_name is not None:
            user.display_name = cmd.display_name
        if cmd.email is not None:
            user.email = cmd.email
        if cmd.status is not None:
            user.status = UserStatus(cmd.status)
        await deps.repository.save(user)
        if cmd.roles is not None:
            await deps.repository.replace_global_roles(cmd.user_id, cmd.roles)

        action = (
            IAM_USER_REACTIVATED if user.status is UserStatus.ACTIVE else IAM_USER_UPDATED
        )
        await deps.bus.publish(
            iam_event(
                action,
                actor_id=cmd.actor_id,
                payload={"user_id": user.id, "username": user.username},
            )
        )
        await deps.audit.record(
            AuditEntry(
                id=deps.ids.new_id(),
                actor_id=cmd.actor_id,
                actor_type="user",
                action=action,
                result="success",
                created_at=deps.time.now(),
                resource_type="user",
                resource_id=user.id,
                detail={
                    "username": user.username,
                    "status": user.status.value,
                    "roles": sorted(role.value for role in user.roles),
                },
            )
        )
        return to_view(user)


class SetAvatarUseCase:
    """El usuario autenticado actualiza su avatar (data URL base64)."""

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: SetAvatarCommand) -> UserView:
        deps = self._deps
        user = await deps.repository.get(cmd.user_id)
        if user is None:
            raise UserNotFoundError(
                f"Usuario no encontrado: {cmd.user_id}",
                context={"user_id": cmd.user_id},
            )
        user.avatar = cmd.avatar
        await deps.repository.save(user)
        await deps.bus.publish(
            iam_event(
                IAM_USER_UPDATED,
                actor_id=cmd.user_id,
                payload={"user_id": user.id, "username": user.username},
            )
        )
        await deps.audit.record(
            AuditEntry(
                id=deps.ids.new_id(),
                actor_id=cmd.user_id,
                actor_type="user",
                action=IAM_USER_UPDATED,
                result="success",
                created_at=deps.time.now(),
                resource_type="user",
                resource_id=user.id,
                detail={"username": user.username, "avatar": "updated"},
            )
        )
        return to_view(user)


class DeleteUserUseCase:
    """Admin suspende un usuario (soft delete; preserva auditoría).

    ``status = 'suspended'`` impide login/refresh; no se borra físicamente para
    no romper referencias de auditoría. La reactivación se hace con
    ``PUT /users/{id}`` y ``status='active'``.
    """

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: DeleteUserCommand) -> None:
        deps = self._deps
        user = await deps.repository.get(cmd.user_id)
        if user is None:
            raise UserNotFoundError(
                f"Usuario no encontrado: {cmd.user_id}",
                context={"user_id": cmd.user_id},
            )
        user.status = UserStatus.SUSPENDED
        await deps.repository.save(user)
        await deps.bus.publish(
            iam_event(
                IAM_USER_SUSPENDED,
                actor_id=cmd.actor_id,
                payload={"user_id": user.id, "username": user.username},
            )
        )
        await deps.audit.record(
            AuditEntry(
                id=deps.ids.new_id(),
                actor_id=cmd.actor_id,
                actor_type="user",
                action=IAM_USER_SUSPENDED,
                result="success",
                created_at=deps.time.now(),
                resource_type="user",
                resource_id=user.id,
                detail={"username": user.username},
            )
        )


class ListRolesUseCase:
    """Devuelve el catálogo base de roles (get: ``iam.view``).

    Los roles built-in viven en ``BuiltinRole`` (sin tabla ``iam_roles`` en el
    mínimo viable); ``id`` es el nombre y el resto es metadata estática.
    """

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps
        del self._deps

    async def execute(self) -> list[RoleView]:
        return [
            RoleView(
                id=role.value,
                name=role.value,
                description=_ROLE_DESCRIPTIONS[role],
                is_system=True,
            )
            for role in BuiltinRole
        ]


class ListAuditLogsUseCase:
    """Admin consulta el audit log con filtros y paginación (get: ``iam.view``)."""

    def __init__(self, deps: IamDeps) -> None:
        self._deps = deps

    async def execute(
        self,
        *,
        actor_id: str | None = None,
        action: str | None = None,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> AuditLogPage:
        records, total = await self._deps.audit.list(
            actor_id=actor_id,
            action=action,
            from_at=from_at,
            to_at=to_at,
            limit=limit,
            offset=offset,
        )
        items = [
            AuditLogView(
                id=record.id,
                actor_id=record.actor_id,
                actor_type=record.actor_type,
                action=record.action,
                resource_type=record.resource_type,
                resource_id=record.resource_id,
                result=record.result,
                detail=record.detail,
                ip=record.ip,
                ua=record.ua,
                created_at=record.created_at,
                hash=record.hash,
                prev_hash=record.prev_hash,
            )
            for record in records
        ]
        return AuditLogPage(items=items, total=total)


_ROLE_DESCRIPTIONS: dict[BuiltinRole, str] = {
    BuiltinRole.SUPER_ADMIN: "Acceso total al panel y a la infraestructura.",
    BuiltinRole.ADMIN: "Gestión completa del panel (usuarios, servidores, ajustes).",
    BuiltinRole.OPERATOR: "Operación de servidores: configuración, control y jugadores.",
    BuiltinRole.VIEWER: "Solo lectura del panel y de los servidores.",
}
