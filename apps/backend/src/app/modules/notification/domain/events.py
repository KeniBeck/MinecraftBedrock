"""Eventos del módulo Notification (Blueprint §3.12, §9).

El gateway reenruta los ``DomainEvent`` del bus a canales del frontend
(``global``, ``server:{id}``, ``user:{id}``) envolviéndolos en un
``EventEnvelope`` (§13.2). Los errores propios de Notification viven aquí;
los tipos de evento se reexportan desde los módulos de origen.
"""

from __future__ import annotations

from app.kernel.errors import AppError

# Reexport de la envoltura WebSocket (§13.2) definida en el kernel.
from app.kernel.events.event import EventEnvelope  # noqa: F401

SCOPE_GLOBAL = "global"
SCOPE_SERVER = "server"
SCOPE_USER = "user"

PREFIX_GLOBAL = "global"
PREFIX_SERVER = "server"
PREFIX_USER = "user"


def channel_name(scope: str, key: str | None) -> str:
    """Nombre canónico de un canal a partir de alcance y clave.

    ``global`` no lleva clave; ``server:{server_id}`` y ``user:{user_id}`` la
    incluyen con el prefijo reservado (Blueprint §3.12).
    """
    if scope == SCOPE_GLOBAL:
        return PREFIX_GLOBAL
    if key is None:
        raise InvalidSubscriptionError("El canal no-global requiere una clave")
    return f"{scope}:{key}"


def parse_channel(name: str) -> tuple[str, str | None]:
    """Descompone un nombre de canal en ``(scope, key)``.

    Acepta ``global``, ``server:{server_id}`` y ``user:{user_id}``. Un nombre
    no reservado o vacío lanza ``InvalidSubscriptionError``.
    """
    if name == PREFIX_GLOBAL:
        return SCOPE_GLOBAL, None
    if name.startswith(f"{PREFIX_SERVER}:") and len(name) > len(PREFIX_SERVER) + 1:
        return SCOPE_SERVER, name[len(PREFIX_SERVER) + 1 :]
    if name.startswith(f"{PREFIX_USER}:") and len(name) > len(PREFIX_USER) + 1:
        return SCOPE_USER, name[len(PREFIX_USER) + 1 :]
    raise InvalidSubscriptionError(f"Canal desconocido: {name!r}")


def event_scope(event_type: str) -> str:
    """Alcance aproximado del envelope a partir del tipo de evento.

    Heurística: los eventos ``SERVER.*``/``CONSOLE.*``/``WORLD.*``/``PLAYER.*``/
    ``BACKUP.*``/``TASK.*``/``CONFIG.*`` se asocian al canal de su
    ``server_id``; los de IAM/AUTH al canal ``user:{actor_id}``; el resto a
    ``global``. El dispatcher decide el canal final priorizando el
    ``server_id`` del evento cuando existe.
    """
    if event_type.startswith("AUTH.") or event_type.startswith("IAM."):
        return SCOPE_USER
    if event_type.startswith(
        (
            "SERVER.",
            "CONSOLE.",
            "WORLD.",
            "PLAYER.",
            "BACKUP.",
            "TASK.",
            "CONFIG.",
        )
    ):
        return SCOPE_SERVER
    return SCOPE_GLOBAL


class NotificationError(AppError):
    """Raíz de errores del módulo Notification (Fase H §16.13)."""

    code = "NOTI.ERROR"


class InvalidSubscriptionError(NotificationError):
    """Canal de suscripción mal formado o no autorizado."""

    code = "NOTI.INVALID_SUBSCRIPTION"


class RateLimitExceededError(NotificationError):
    """Un cliente superó la cuota de mensajes por segundo."""

    code = "NOTI.RATE_LIMIT_EXCEEDED"


class ResumeTooLargeError(NotificationError):
    """El reenvío de ``resume`` supera el backlog máximo configurado."""

    code = "NOTI.RESUME_TOO_LARGE"
