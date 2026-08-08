"""Puertos de la aplicación Permission (Blueprint §3.6, §4.2)."""

from __future__ import annotations

from typing import Protocol

from app.kernel.ports.storage import ServerStoragePort


class PermissionStorageResolver(Protocol):
    """Resuelve el ``ServerStoragePort`` por ``server_id``."""

    def for_server(self, server_id: str) -> ServerStoragePort: ...
