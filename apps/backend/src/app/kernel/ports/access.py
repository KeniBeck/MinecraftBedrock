"""Contrato ``AccessControlPort`` (Blueprint §4.5, TDD §14.2).

Decisiones de autorización centralizadas en IAM. Ningún módulo implementa su
propia comprobación; las decisiones sensibles se auditan.

Ajuste (Fase C paso 8): las operaciones son async porque IAM persiste en
Postgres (repositorio async). El puerto no tenía consumidores en el momento
del ajuste; Presentación (Fase D/H) lo inyectará tal cual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Identity:
    """Identidad autenticada (emitida por IAM)."""

    id: str
    username: str
    roles: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Decisión de autorización: booleana + motivo (Blueprint §4.5)."""

    allowed: bool
    reason: str = ""


class AccessControlPort(Protocol):
    """Autentica y autoriza acciones (RBAC global + ACL por servidor)."""

    async def authenticate(self, credentials: Any) -> Identity:
        """Devuelve la identidad autenticada o rechaza (lanza error)."""

    async def authorize(
        self,
        identity: Identity,
        action: str,
        resource: str | None = None,
    ) -> AuthorizationDecision:
        """Evalúa roles globales y membresías por servidor."""

    def subject(self, identity: Identity) -> Any:
        """Resuelve el actor para auditoría."""
