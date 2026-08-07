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
from datetime import timedelta

from app.kernel.events.bus import EventBusPort
from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.access import Identity
from app.kernel.ports.settings import SettingsPort
from app.kernel.time import TimeProviderPort
from app.modules.iam.application.commands import (
    AssignMembershipCommand,
    AssignRoleCommand,
    CreateUserCommand,
    LoginCommand,
    LogoutCommand,
    RefreshCommand,
)
from app.modules.iam.application.ports import (
    AuditEntry,
    AuditStorePort,
    PasswordHasher,
    Session,
    SessionStorePort,
    TokenService,
)
from app.modules.iam.application.results import AuthResult, UserView
from app.modules.iam.domain.errors import (
    AccountSuspendedError,
    InvalidCredentialsError,
    TokenExpiredError,
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
    iam_event,
)
from app.modules.iam.domain.repository import IamRepositoryPort
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
