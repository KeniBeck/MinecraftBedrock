"""Puerto de persistencia del módulo IAM (Blueprint §4.8, TDD §13.2).

Protocol estructural implementado por infraestructura (Postgres en producción,
en memoria para tests). El dominio declara la interfaz; ``User`` es la autoridad
del estado; los roles globales y las membresías se consultan por separado.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.modules.iam.domain.permissions import PermissionCode
from app.modules.iam.domain.role import BuiltinRole, ServerMembership
from app.modules.iam.domain.user import User


class IamRepositoryPort(Protocol):
    """Persistencia del agregado ``User`` y sus asociaciones."""

    async def save(self, user: User) -> None:
        """Inserta o actualiza el usuario (upsert)."""

    async def get(self, user_id: str) -> User | None:
        """Devuelve el usuario con sus roles globales, o ``None``."""

    async def get_by_username(self, username: str) -> User | None:
        """Devuelve el usuario por ``username``, o ``None``."""

    async def add_global_role(self, user_id: str, role: BuiltinRole) -> None:
        """Concede un rol global al usuario (idempotente)."""

    async def add_membership(self, user_id: str, server_id: str, role: BuiltinRole) -> None:
        """Concede/actualiza la membresía del usuario sobre el servidor."""

    async def list_memberships(self, user_id: str) -> Sequence[ServerMembership]:
        """Devuelve las membresías del usuario (ACL por servidor)."""

    async def touch_last_login(self, user_id: str, at: datetime) -> None:
        """Actualiza el timestamp del último login."""


class PermissionRepositoryPort(Protocol):
    """Matriz de permisos por acción (catalogo ``iam_permissions``/``iam_role_permissions``)."""

    async def list_permissions(self) -> Sequence[PermissionCode]:
        """Devuelve el catálogo completo de códigos de permiso."""

    async def permissions_for_role(self, role: BuiltinRole) -> frozenset[str]:
        """Devuelve los códigos de permiso que concede un rol (matriz sembrada)."""

    async def seed_catalog(self) -> None:
        """Sembra el catálogo base si no está (idempotente)."""
