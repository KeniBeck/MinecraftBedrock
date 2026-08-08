"""Facade pública del módulo Notification (Blueprint §3.12).

Capa de aplicación del gateway: agenda y difunde eventos del bus a canales,
gestiona suscripciones por conexión y reenvía eventos perdidos (resume). La
capa de API (presentación) usa esta facade; aquí no se decide autenticación
(eso vive en ``bootstrap/security``), solo autorización de canales vía
``AccessControlPort``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.access import AccessControlPort, Identity
from app.kernel.time import TimeProviderPort
from app.modules.notification.application.connection_manager import (
    ClientConnection,
    ConnectionManager,
)
from app.modules.notification.application.event_dispatcher import EventDispatcher
from app.modules.notification.application.rate_limiter import (
    RateLimitConfig,
    TokenBucketRateLimiter,
)
from app.modules.notification.application.resume_handler import ResumeHandler
from app.modules.notification.domain.repository import EventLogRepositoryPort
from app.modules.notification.domain.subscription import Channel, ChannelAuthorizer


@dataclass(frozen=True, slots=True)
class SubscriptionResult:
    """Resultado de suscribir una conexión a un canal."""

    channel: str
    allowed: bool
    reason: str = ""


class NotificationFacade:
    """Capa de aplicación del gateway (Blueprint §3.12)."""

    def __init__(
        self,
        *,
        connections: ConnectionManager,
        dispatcher: EventDispatcher,
        authorizer: ChannelAuthorizer,
        resume: ResumeHandler,
        rate_config: RateLimitConfig,
        time: TimeProviderPort,
        ids: IdGeneratorPort,
        event_log: EventLogRepositoryPort,
    ) -> None:
        self.connections = connections
        self._dispatcher = dispatcher
        self._authorizer = authorizer
        self._resume = resume
        self._rate_config = rate_config
        self._time = time
        self._ids = ids
        self.event_log = event_log

    @classmethod
    def build(
        cls,
        *,
        access: AccessControlPort,
        event_log: EventLogRepositoryPort,
        ids: IdGeneratorPort,
        time: TimeProviderPort,
        rate_config: RateLimitConfig | None = None,
        resume_limit: int = 1000,
    ) -> NotificationFacade:
        """Compone el facade con sus componentes (sin registrar el bus)."""
        connections = ConnectionManager()
        dispatcher = EventDispatcher(connections=connections, event_log=event_log)
        return cls(
            connections=connections,
            dispatcher=dispatcher,
            authorizer=ChannelAuthorizer(access),
            resume=ResumeHandler(event_log, limit=resume_limit),
            rate_config=rate_config or RateLimitConfig(),
            time=time,
            ids=ids,
            event_log=event_log,
        )

    @property
    def dispatcher(self) -> EventDispatcher:
        return self._dispatcher

    def open_connection(self, identity: Identity) -> ClientConnection:
        """Registra una nueva conexión con su limiter de salida."""
        connection = ClientConnection(
            connection_id=self._ids.new_id(),
            identity=identity,
        )
        connection.rate_limiter = TokenBucketRateLimiter(self._rate_config, self._time)
        self.connections.register(connection)
        return connection

    def close_connection(self, connection: ClientConnection) -> None:
        self.connections.unregister(connection.connection_id)

    async def subscribe(
        self, connection: ClientConnection, identity: Identity, channel: Channel
    ) -> SubscriptionResult:
        """Suscribe la conexión a un canal (o devuelve el motivo si no puede)."""
        decision = await self._authorizer.authorize(identity, channel)
        if not decision.allowed:
            return SubscriptionResult(channel.name, False, decision.reason)
        self.connections.subscribe(connection.connection_id, channel.name)
        return SubscriptionResult(channel.name, True, "")

    async def unsubscribe(self, connection: ClientConnection, channel: Channel) -> None:
        self.connections.unsubscribe(connection.connection_id, channel.name)

    async def resume(
        self, last_seq: int, channels: list[str]
    ) -> tuple[list[dict[str, object]], bool]:
        """Reenvía eventos posteriores a un ``seq``; ``(envelopes, exceeded)``."""
        result = await self._resume.resume(last_seq, channels)
        return result.envelopes, result.exceeded
