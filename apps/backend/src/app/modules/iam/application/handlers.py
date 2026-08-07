"""Handlers de eventos consumidos por IAM (Blueprint §3.1).

``SERVER.CRASHED``, ``TASK.FAILED`` y ``BACKUP.FAILED`` se registran en el
audit log básico. Son **defensivos**: si el evento nunca llega no pasa nada, y
un fallo de auditoría no propaga (se loguea y se sigue) para no romper el flujo
del publicador.
"""

from __future__ import annotations

import logging

from app.kernel.events.event import DomainEvent
from app.kernel.ids import IdGeneratorPort
from app.kernel.time import TimeProviderPort
from app.modules.iam.application.ports import AuditEntry, AuditStorePort

logger = logging.getLogger(__name__)

SERVER_CRASHED_TOPIC = "server.crashed"
TASK_FAILED_TOPIC = "task.failed"
BACKUP_FAILED_TOPIC = "backup.failed"


class IncidentAuditHandler:
    """Registra en el audit log un incidente publicado por otro módulo."""

    def __init__(
        self,
        audit: AuditStorePort,
        ids: IdGeneratorPort,
        time: TimeProviderPort,
        action: str,
        resource_type: str,
    ) -> None:
        self._audit = audit
        self._ids = ids
        self._time = time
        self._action = action
        self._resource_type = resource_type

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id
        if not server_id:
            return
        try:
            await self._audit.record(
                AuditEntry(
                    id=self._ids.new_id(),
                    actor_id=event.actor_id,
                    actor_type="system",
                    action=self._action,
                    result="failure",
                    created_at=self._time.now(),
                    resource_type=self._resource_type,
                    resource_id=server_id,
                    detail=dict(event.payload),
                )
            )
        except Exception:  # noqa: BLE001 — audit defensivo, no debe romper el bus
            logger.warning("IAM audit falló para %s", self._action, exc_info=True)
