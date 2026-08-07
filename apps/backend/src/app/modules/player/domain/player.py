"""Entidad ``Player`` (Blueprint §3.5: caché de presencia e historial).

Un ``Player`` es la identidad persistida del jugador (XUID primario, jamás el
gamertag como identidad única — §16.6) con su nombre conocido, primeras/últimas
visitas y el playtime acumulado (segundos). ``playtime_seconds`` es la suma de
las sesiones cerradas; las sesiones abiertas no suman hasta cerrarse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Player:
    """Jugador conocido por el panel (identidad = XUID)."""

    xuid: str
    name: str
    first_seen_at: datetime
    last_seen_at: datetime
    playtime_seconds: int
    created_at: datetime
    updated_at: datetime
