"""Puertos técnicos del kernel (Blueprint §1.2).

Viven en el kernel compartido (no en el dominio de un módulo) para permitir
que varios dominios consuman capacidades técnicas sin dependencias cruzadas.
"""

from app.kernel.ports.access import AccessControlPort, AuthorizationDecision, Identity
from app.kernel.ports.backups import BackupStorePort
from app.kernel.ports.runtime import RuntimeSpec, RuntimeState, ServerRuntimePort, ServerState
from app.kernel.ports.settings import SettingsPort
from app.kernel.ports.status import ProbeResult, StatusProbePort
from app.kernel.ports.storage import ServerStoragePort

__all__ = [
    "AccessControlPort",
    "AuthorizationDecision",
    "BackupStorePort",
    "Identity",
    "ProbeResult",
    "RuntimeSpec",
    "RuntimeState",
    "ServerRuntimePort",
    "ServerState",
    "ServerStoragePort",
    "SettingsPort",
    "StatusProbePort",
]
