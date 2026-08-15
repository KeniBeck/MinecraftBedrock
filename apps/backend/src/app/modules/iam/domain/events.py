"""Eventos de dominio ``AUTH.*`` e ``IAM.*`` (Blueprint §9.7).

Se publican únicamente vía ``EventBusPort`` (ADR-001). Los temas de los eventos
consumidos por IAM (``SERVER.CRASHED``, ``TASK.FAILED``, ``BACKUP.FAILED``) se
derivan con ``topic_for`` (Blueprint §10.3): ``server.crashed``, ``task.failed``,
``backup.failed``.
"""

from __future__ import annotations

from typing import Any

from app.kernel.events.event import DomainEvent

AUTH_LOGIN_SUCCESS = "AUTH.LOGIN_SUCCESS"
AUTH_LOGIN_FAILED = "AUTH.LOGIN_FAILED"
IAM_USER_CREATED = "IAM.USER_CREATED"
IAM_USER_ROLE_CHANGED = "IAM.USER_ROLE_CHANGED"
IAM_USER_UPDATED = "IAM.USER_UPDATED"
IAM_USER_SUSPENDED = "IAM.USER_SUSPENDED"
IAM_USER_REACTIVATED = "IAM.USER_REACTIVATED"

SERVER_CRASHED_TOPIC = "server.crashed"
TASK_FAILED_TOPIC = "task.failed"
BACKUP_FAILED_TOPIC = "backup.failed"


def topic_for(event_type: str) -> str:
    """Tema de suscripción derivado del tipo (Blueprint §10.3)."""
    return event_type.lower()


def iam_event(
    event_type: str,
    *,
    actor_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> DomainEvent:
    """Construye un evento de dominio ``AUTH.*``/``IAM.*`` normalizado."""
    return DomainEvent(
        type=event_type,
        event_id="",
        actor_id=actor_id,
        payload=payload or {},
    )
