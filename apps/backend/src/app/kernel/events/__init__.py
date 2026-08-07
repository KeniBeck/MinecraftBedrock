"""Eventos del kernel: contrato del bus y tipos base."""

from app.kernel.events.bus import EventBusPort, EventHandler
from app.kernel.events.event import DomainEvent, EventEnvelope

__all__ = ["DomainEvent", "EventBusPort", "EventEnvelope", "EventHandler"]
