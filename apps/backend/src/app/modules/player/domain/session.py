"""``PlaySession`` (Blueprint §3.5: sesión de juego de un jugador).

Una sesión se abre con ``PLAYER.JOINED`` y se cierra con ``PLAYER.LEFT`` o se
aborta cuando el servidor se reinicia (``SERVER.STARTED`` limpia la presencia).
Las sesiones abortadas no acumulan playtime: al cortarse la conexión se
desconoce el momento real del fin y no se debe sobre-contar tiempo en el que el
servidor estuvo caído.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SessionEndReason(StrEnum):
    """Motivo del cierre de una sesión."""

    LEFT = "left"
    ABORTED = "aborted"


@dataclass(frozen=True, slots=True)
class PlaySession:
    """Presencia de un jugador en un servidor entre ``joined_at`` y ``left_at``."""

    id: str
    server_id: str
    xuid: str
    joined_at: datetime
    left_at: datetime | None = None
    reason: SessionEndReason | None = None
    playtime_seconds: int = 0

    def elapsed_seconds(self, now: datetime) -> int:
        """Segundos de duración de la sesión (hasta ``left_at`` o ``now``)."""
        end = self.left_at if self.left_at is not None else now
        return max(0, int((end - self.joined_at).total_seconds()))
