"""Puerto ``TimeProviderPort`` (Blueprint §1.2).

Reloj inyectable para dominios que dependen del tiempo (Scheduler, Backup,
Monitoring). La implementación concreta vive en ``infrastructure/common``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class TimeProviderPort(Protocol):
    """Provee la hora actual (UTC, timezone-aware)."""

    def now(self) -> datetime:
        """Devuelve la hora UTC actual."""
