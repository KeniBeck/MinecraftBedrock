"""Kernel compartido (Shared kernel, TDD §16).

Contiene los puertos técnicos del kernel (Blueprint §1.2), la jerarquía de
errores (§11), el bus/eventos (§7 y §9), IDs y tiempo. El kernel NO conoce
los dominios.
"""

from app.kernel.errors import (
    AppError,
    BusinessRuleViolation,
    ConcurrencyConflictError,
    DomainError,
    HttpError,
    InfrastructureError,
    InvalidStateError,
    NotFoundError,
    UnexpectedError,
    ValidationError,
)
from app.kernel.events.bus import EventBusPort
from app.kernel.events.event import DomainEvent, EventEnvelope
from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.access import AccessControlPort, AuthorizationDecision, Identity
from app.kernel.ports.backups import BackupStorePort
from app.kernel.ports.runtime import RuntimeSpec, RuntimeState, ServerRuntimePort, ServerState
from app.kernel.ports.settings import SettingsPort
from app.kernel.ports.status import ProbeResult, StatusProbePort
from app.kernel.ports.storage import ServerStoragePort
from app.kernel.time import TimeProviderPort

__all__ = [
    "AccessControlPort",
    "AppError",
    "AuthorizationDecision",
    "BackupStorePort",
    "BusinessRuleViolation",
    "ConcurrencyConflictError",
    "DomainError",
    "DomainEvent",
    "EventBusPort",
    "EventEnvelope",
    "HttpError",
    "IdGeneratorPort",
    "Identity",
    "InfrastructureError",
    "InvalidStateError",
    "NotFoundError",
    "ProbeResult",
    "RuntimeSpec",
    "RuntimeState",
    "ServerRuntimePort",
    "ServerState",
    "ServerStoragePort",
    "SettingsPort",
    "StatusProbePort",
    "TimeProviderPort",
    "UnexpectedError",
    "ValidationError",
]
