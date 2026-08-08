"""Tests del dominio de suscripción (canales y autorización, Fase H §16.13)."""

from __future__ import annotations

from typing import Any

import pytest

from app.kernel.ports.access import AuthorizationDecision, Identity
from app.modules.notification.domain.events import InvalidSubscriptionError
from app.modules.notification.domain.subscription import Channel, ChannelAuthorizer


class FakeAccess:
    """``AccessControlPort`` con decisiones inyectadas por servidor."""

    def __init__(self) -> None:
        self.allowed_servers: set[str] = set()

    async def authenticate(self, credentials: Any) -> Identity:
        return identity()

    async def authorize(
        self,
        identity: Identity,
        action: str,
        resource: str | None = None,
    ) -> AuthorizationDecision:
        del identity, action
        allowed = resource in self.allowed_servers
        return AuthorizationDecision(allowed=allowed, reason="ok" if allowed else "sin membresía")

    def subject(self, identity: Identity) -> Any:
        return identity


def identity(uid: str = "u1") -> Identity:
    return Identity(id=uid, username="usuario", roles=("viewer",))


class TestChannel:
    def test_nombres_canonicos(self) -> None:
        assert Channel.parse("global").name == "global"
        assert Channel.parse("server:abc-123").name == "server:abc-123"
        assert Channel.parse("user:u1").name == "user:u1"

    def test_invalidos(self) -> None:
        for bad in ["", "foo", "server:", "user:", "global:x"]:
            with pytest.raises(InvalidSubscriptionError):
                Channel.parse(bad)


class TestChannelAuthorizer:
    async def test_global_abierto(self) -> None:
        auth = ChannelAuthorizer(FakeAccess())
        decision = await auth.authorize(identity(), Channel.parse("global"))
        assert decision.allowed

    async def test_user_propio(self) -> None:
        auth = ChannelAuthorizer(FakeAccess())
        decision = await auth.authorize(identity("u1"), Channel.parse("user:u1"))
        assert decision.allowed

    async def test_user_ajeno_rechazado(self) -> None:
        auth = ChannelAuthorizer(FakeAccess())
        decision = await auth.authorize(identity("u1"), Channel.parse("user:u2"))
        assert not decision.allowed

    async def test_server_con_membresia(self) -> None:
        access = FakeAccess()
        access.allowed_servers = {"s1"}
        auth = ChannelAuthorizer(access)
        decision = await auth.authorize(identity(), Channel.parse("server:s1"))
        assert decision.allowed

    async def test_server_sin_membresia_rechazado(self) -> None:
        access = FakeAccess()
        access.allowed_servers = {"s2"}
        auth = ChannelAuthorizer(access)
        decision = await auth.authorize(identity(), Channel.parse("server:s1"))
        assert not decision.allowed
