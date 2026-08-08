"""Servicio de control de acceso (Blueprint §4.5, technical-design §14.2).

Implementación de ``AccessControlPort`` con matriz de permisos por acción
(Fase H paso 18). La autorización se evalúa así:

1. Rol global ``super_admin`` → autorizado siempre.
2. Rol global ``admin`` → autorizado siempre (gestión de cualquier recurso).
3. Ámbito panel (``resource is None`` o ``"panel"``): la acción debe ser una
   acción de panel (``PANEL_ACTIONS``) y estar en la matriz del rol global.
   Como solo admin/super_admin poseen acciones de panel, esto equivale a
   "requiere admin global" para el resto.
4. Ámbito servidor (``resource`` = ``server:{id}`` o ``{server_id}``): el rol
   de la membresía del usuario sobre ese servidor debe conceder la acción.

La matriz se lee vía ``PermissionRepositoryPort`` (Postgres en producción,
estática en memoria para tests); el dominio la define en ``permissions.py``.
"""

from __future__ import annotations

from typing import Any

from app.kernel.ports.access import AuthorizationDecision, Identity
from app.modules.iam.application.commands import LoginCommand, LoginCredentials
from app.modules.iam.application.use_cases import LoginUseCase
from app.modules.iam.domain.errors import TokenInvalidError
from app.modules.iam.domain.permissions import PANEL_ACTIONS, READ_ACTIONS
from app.modules.iam.domain.repository import IamRepositoryPort, PermissionRepositoryPort
from app.modules.iam.domain.role import BuiltinRole
from app.modules.iam.infrastructure.memory import InMemoryPermissionRepository

# Re-export para compatibilidad (tests/consumidores previos importan READ_ACTIONS
# desde ``application.access``).
__all__ = ["READ_ACTIONS"]


class AccessControlService:
    """Decide autorizaciones (único punto, Blueprint §4.5)."""

    def __init__(
        self,
        login: LoginUseCase,
        repository: IamRepositoryPort,
        permissions: PermissionRepositoryPort | None = None,
    ) -> None:
        self._login = login
        self._repository = repository
        self._permissions = permissions or InMemoryPermissionRepository()

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
        if identity.is_api_key and action not in identity.scopes:
            return AuthorizationDecision(
                False,
                f"la API key no tiene el scope {action}",
            )

        global_roles = self._parse_roles(identity.roles)
        if BuiltinRole.SUPER_ADMIN in global_roles:
            return AuthorizationDecision(True, "super_admin global")
        if BuiltinRole.ADMIN in global_roles:
            return AuthorizationDecision(True, "admin global")

        scope, server_id = self._normalize_resource(resource)
        if scope == "panel":
            return await self._decide_panel(global_roles, action)
        return await self._decide_server(identity.id, server_id, action)

    async def _decide_panel(
        self, global_roles: set[BuiltinRole], action: str
    ) -> AuthorizationDecision:
        if action not in PANEL_ACTIONS:
            return AuthorizationDecision(
                False,
                "la acción no es de ámbito panel (se exige recurso de servidor)",
            )
        for role in global_roles:
            granted = await self._permissions_for(role)
            if action in granted:
                return AuthorizationDecision(True, f"permiso en rol global {role.value}")
        return AuthorizationDecision(False, "se requiere rol global admin o super_admin")

    async def _decide_server(
        self, user_id: str, server_id: str, action: str
    ) -> AuthorizationDecision:
        memberships = await self._repository.list_memberships(user_id)
        membership = next((m for m in memberships if m.server_id == server_id), None)
        if membership is None:
            return AuthorizationDecision(False, "sin membresía en el servidor")
        granted = await self._permissions_for(membership.role)
        if action in granted:
            return AuthorizationDecision(
                True,
                f"membresía {membership.role.value} concede {action}",
            )
        return AuthorizationDecision(
            False,
            f"la membresía {membership.role.value} no concede {action}",
        )

    async def _permissions_for(self, role: BuiltinRole) -> frozenset[str]:
        return await self._permissions.permissions_for_role(role)

    def subject(self, identity: Identity) -> Any:
        return {"id": identity.id, "username": identity.username, "roles": identity.roles}

    @staticmethod
    def _normalize_resource(resource: str | None) -> tuple[str, str]:
        """Devuelve ``(scope, server_id)`` para panel/servidor."""
        if resource is None or resource == "panel":
            return "panel", ""
        if resource.startswith("server:"):
            return "server", resource[len("server:") :]
        return "server", resource

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
