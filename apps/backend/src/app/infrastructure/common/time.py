"""Implementación de ``TimeProviderPort`` (reloj del sistema, UTC)."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemTimeProvider:
    """Devuelve la hora UTC actual."""

    def now(self) -> datetime:
        return datetime.now(UTC)
