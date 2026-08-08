"""Suscripciones a canales del gateway (Blueprint §3.12).

Un ``Channel`` identifica un destino de difusión: ``global``, ``server:{id}``
o ``user:{id}``. La autorización se delega en ``AccessControlPort`` (IAM):
suscribirse a ``server:{id}`` exige membresía (viewer u operator según la
lectura); ``global`` y ``user:{mismo usuario}`` se permiten siempre.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.kernel.ports.access import AccessControlPort, Identity
from app.modules.notification.domain.events import (
    SCOPE_GLOBAL,
    SCOPE_SERVER,
    SCOPE_USER,
    InvalidSubscriptionError,
    channel_name,
    parse_channel,
)

# Acción de lectura usada para validar membresía sobre un servidor (visión).
_SERVER_READ_ACTION = "server.view"


@dataclass(frozen=True, slots=True)
class Channel:
    """Canal de suscripción con su nombre canónico."""

    scope: str
    key: str | None = None

    @property
    def name(self) -> str:
        return channel_name(self.scope, self.key)

    @classmethod
    def parse(cls, name: str) -> Channel:
        scope, key = parse_channel(name)
        return cls(scope=scope, key=key)


@dataclass(frozen=True, slots=True)
class SubscriptionDecision:
    """Resultado de autorizar una suscripción: permitida + razón."""

    allowed: bool
    reason: str = ""


class ChannelAuthorizer:
    """Autoriza suscripciones a canales vía ``AccessControlPort`` (IAM)."""

    def __init__(self, access: AccessControlPort) -> None:
        self._access = access

    async def authorize(self, identity: Identity, channel: Channel) -> SubscriptionDecision:
        """Valida que ``identity`` pueda suscribirse a ``channel``."""
        if channel.scope == SCOPE_GLOBAL:
            return SubscriptionDecision(True, "canal global abierto")
        if channel.scope == SCOPE_USER:
            if identity.id == channel.key:
                return SubscriptionDecision(True, "canal del propio usuario")
            return SubscriptionDecision(False, "no es el propio usuario")
        if channel.scope == SCOPE_SERVER:
            if channel.key is None:
                return SubscriptionDecision(False, "canal de servidor sin servidor")
            decision = await self._access.authorize(identity, _SERVER_READ_ACTION, channel.key)
            return SubscriptionDecision(decision.allowed, decision.reason)
        raise InvalidSubscriptionError(f"Alcance desconocido: {channel.scope}")
