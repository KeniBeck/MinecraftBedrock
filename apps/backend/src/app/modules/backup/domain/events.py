"""Eventos de dominio ``BACKUP.*`` (Blueprint §3.4, §9.4).

Backup publica el ciclo de vida del backup (started/progress/completed/
failed/validated/deleted) y de la restauración (restore_started/completed/
failed). Consume ``WORLD.DELETED`` (``WorldDeletedHandler``) para marcar
huérfanos (§9.3) y, en Fase G, ``TASK.STARTED`` (backup programado) — el
Scheduler es el paso 15, aún no existe.
"""

from __future__ import annotations

from app.kernel.events.event import DomainEvent

BACKUP_STARTED = "BACKUP.STARTED"
BACKUP_PROGRESS = "BACKUP.PROGRESS"
BACKUP_COMPLETED = "BACKUP.COMPLETED"
BACKUP_FAILED = "BACKUP.FAILED"
BACKUP_RESTORE_STARTED = "BACKUP.RESTORE_STARTED"
BACKUP_RESTORE_COMPLETED = "BACKUP.RESTORE_COMPLETED"
BACKUP_RESTORE_FAILED = "BACKUP.RESTORE_FAILED"
BACKUP_DELETED = "BACKUP.DELETED"
BACKUP_VALIDATED = "BACKUP.VALIDATED"

BACKUP_STARTED_TOPIC = "backup.started"
BACKUP_PROGRESS_TOPIC = "backup.progress"
BACKUP_COMPLETED_TOPIC = "backup.completed"
BACKUP_FAILED_TOPIC = "backup.failed"
BACKUP_RESTORE_STARTED_TOPIC = "backup.restore_started"
BACKUP_RESTORE_COMPLETED_TOPIC = "backup.restore_completed"
BACKUP_RESTORE_FAILED_TOPIC = "backup.restore_failed"
BACKUP_DELETED_TOPIC = "backup.deleted"
BACKUP_VALIDATED_TOPIC = "backup.validated"


def backup_event(
    event_type: str,
    server_id: str,
    world_name: str,
    *,
    actor_id: str | None = None,
    extra: dict[str, object] | None = None,
) -> DomainEvent:
    """Construye un evento ``BACKUP.*`` normalizado (payload canónico)."""
    payload: dict[str, object] = {"server_id": server_id, "world_name": world_name}
    if extra:
        payload.update(extra)
    return DomainEvent(
        type=event_type,
        event_id="",
        server_id=server_id,
        actor_id=actor_id,
        payload=payload,
    )
