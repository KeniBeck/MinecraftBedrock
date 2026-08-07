"""Servicio de control de acceso (Bluepring §4.5, technical-design §14.2).

Implementación de ``AccessControlPort`` en la capa de aplicación: RBAC global +
ACL por servidor, sin matriz de permisos por acción (eso es Fase H). La
clasificación lectura/escritura es un conjunto explícito y documentado de
acciones de lectura; el resto se trata como escritura.

Jerarquía: super_admin(4) > admin(3) > operator(2) > viewer(1).
- Recurso ``None`` (acción de panel): requiere admin o super_admin.
- Recurso servidor: admin/super_admin globales tienen acceso a cualquier servidor;
  operador/viewer solo a servidores con membresía, y el rol de la membresía es
  autoritativo para ese servidor (least privilege): lectura ≥ viewer, escritura ≥
  operator.
"""

from __future__ import annotations

from typing import Any

from app.kernel.ports.access import AuthorizationDecision, Identity
from app.modules.iam.application.commands import LoginCommand, LoginCredentials
from app.modules.iam.application.use_cases import LoginUseCase
from app.modules.iam.domain.errors import TokenInvalidError
from app.modules.iam.domain.repository import IamRepositoryPort
from app.modules.iam.domain.role import ROLE_LEVEL, BuiltinRole

# Acciones de solo lectura conocidas. Sin matriz de permisos (Fase H): todo lo
# que no está aquí se considera escritura.
READ_ACTIONS: frozenset[str] = frozenset(
    {
        "server.view",
        "server.status",
        "server.list",
        "server.console.read",
        "server.status.read",
        "world.list",
        "world.view",
        "world.export",
        "backup.list",
        "backup.view",
        "backup.download",
        "player.list",
        "player.view",
        "player.sessions",
        "player.online",
        "audit.view",
        "iam.user.list",
    }
)


class AccessControlService:
    """Decide autorizaciones (único punto, Bluepring §4.5)."""

    def __init__(self, login: LoginUseCase, repository: IamRepositoryPort) -> None:
        self._login = login
        self._repository = repository

    async def authenticate(self, credentials: Any) -> Identity:
        if not isinstance(credentials, LoginCredentials):
            raise TokenInvalidError("Credenciales de formato inesperado")
        result = await self._login.execute(
            LoginCommand(
                username=credentials.username,
                password=credentials.password,
                ip=credentials.ip,
                ua=credentials.ua,
            )
        )
        return result.identity

    async def authorize(
        self,
        identity: Identity,
        action: str,
        resource: str | None = None,
    ) -> AuthorizationDecision:
        global_level = max(
            (ROLE_LEVEL.get(role, 0) for role in self._parse_roles(identity.roles)),
            default=0,
        )

        if resource is None:
            allowed = global_level >= ROLE_LEVEL[BuiltinRole.ADMIN]
            return AuthorizationDecision(
                allowed,
                reason=(
                    "rol global admin/super_admin"
                    if allowed
                    else "se requiere rol global admin o super_admin"
                ),
            )

        # Admin/super_admin global: gestión de cualquier servidor (design §14.2),
        # sin depender de membresías.
        if global_level >= ROLE_LEVEL[BuiltinRole.ADMIN]:
            return AuthorizationDecision(True, "admin/super_admin global")

        # Operador/viewer: acceso solo a servidores asignados, y el rol de la
        # membresía es autoritativo para ese servidor (least privilege). Sin
        # membresía no hay acceso, aunque exista un rol global.
        memberships = await self._repository.list_memberships(identity.id)
        membership_level = max(
            (
                ROLE_LEVEL.get(membership.role, 0)
                for membership in memberships
                if membership.server_id == resource
            ),
            default=0,
        )
        if membership_level == 0:
            return AuthorizationDecision(
                False,
                "sin membresía en el servidor",
            )

        if action in READ_ACTIONS:
            allowed = membership_level >= ROLE_LEVEL[BuiltinRole.VIEWER]
            return AuthorizationDecision(
                allowed,
                reason=(
                    "membresía viewer o superior"
                    if allowed
                    else "sin acceso de lectura al servidor"
                ),
            )

        allowed = membership_level >= ROLE_LEVEL[BuiltinRole.OPERATOR]
        return AuthorizationDecision(
            allowed,
            reason=(
                "membresía operator o superior"
                if allowed
                else "se requiere operator/admin/super_admin para escritura"
            ),
        )

    def subject(self, identity: Identity) -> Any:
        return {"id": identity.id, "username": identity.username, "roles": identity.roles}

    @staticmethod
    def _parse_roles(roles: tuple[str, ...]) -> set[BuiltinRole]:
        parsed: set[BuiltinRole] = set()
        for name in roles:
            try:
                parsed.add(BuiltinRole(name))
            except ValueError:
                # Rol desconocido en el token: se ignora (token emitido por IAM
                # con un rol ya no del catálogo, o catálogo cambiado).
                continue
        return parsed
