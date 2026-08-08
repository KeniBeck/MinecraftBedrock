"""Capa de aplicación del módulo Notification (Fase H §16.13)."""

from app.modules.notification.application.connection_manager import (
    ClientConnection,
    ConnectionManager,
)
from app.modules.notification.application.event_dispatcher import (
    EventDispatcher,
    resolve_channels,
    serialize_envelope,
)
from app.modules.notification.application.facade import (
    NotificationFacade,
    SubscriptionResult,
)
from app.modules.notification.application.rate_limiter import (
    RateLimitConfig,
    TokenBucketRateLimiter,
)
from app.modules.notification.application.resume_handler import ResumeHandler, ResumeResult

__all__ = [
    "ClientConnection",
    "ConnectionManager",
    "EventDispatcher",
    "resolve_channels",
    "serialize_envelope",
    "NotificationFacade",
    "SubscriptionResult",
    "RateLimitConfig",
    "TokenBucketRateLimiter",
    "ResumeHandler",
    "ResumeResult",
]
