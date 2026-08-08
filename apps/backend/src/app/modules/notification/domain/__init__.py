"""Dominio del módulo Notification: canales, suscripciones y ``EventLog``."""

from app.modules.notification.domain.events import (
    SCOPE_GLOBAL,
    SCOPE_SERVER,
    SCOPE_USER,
    InvalidSubscriptionError,
    NotificationError,
    RateLimitExceededError,
    ResumeTooLargeError,
    channel_name,
    event_scope,
    parse_channel,
)
from app.modules.notification.domain.repository import (
    EventLogEntry,
    EventLogRepositoryPort,
)
from app.modules.notification.domain.subscription import (
    Channel,
    ChannelAuthorizer,
    SubscriptionDecision,
)

__all__ = [
    "NotificationError",
    "InvalidSubscriptionError",
    "RateLimitExceededError",
    "ResumeTooLargeError",
    "SCOPE_GLOBAL",
    "SCOPE_SERVER",
    "SCOPE_USER",
    "channel_name",
    "parse_channel",
    "event_scope",
    "EventLogEntry",
    "EventLogRepositoryPort",
    "Channel",
    "ChannelAuthorizer",
    "SubscriptionDecision",
]
