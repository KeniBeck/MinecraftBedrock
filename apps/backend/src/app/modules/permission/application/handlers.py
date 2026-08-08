"""Handlers del módulo Permission (Blueprint §3.6).

Consume ``PLAYER.JOINED`` para autocompletar el XUID de entradas pendientes
en la allowlist que solo tengan nombre (sin XUID resuelto).
"""

from __future__ import annotations

import json
from typing import Any

from app.kernel.events.bus import EventBusPort
from app.kernel.events.event import DomainEvent
from app.kernel.logging import get_logger
from app.modules.permission.application.ports import PermissionStorageResolver
from app.modules.player.domain.events import PLAYER_JOINED_TOPIC

_ALLOWLIST_FILE = "allowlist.json"

logger = get_logger(__name__)


class AllowlistXuidResolver:
    """Al recibir ``PLAYER.JOINED``, completa entradas de allowlist sin XUID.

    Defensivo: si algo falla solo loguea, no rompe el bus.
    """

    def __init__(self, storage: PermissionStorageResolver, bus: EventBusPort) -> None:
        self._storage = storage
        self._bus = bus

    def register(self) -> None:
        self._bus.subscribe(PLAYER_JOINED_TOPIC, self._on_player_joined)

    def _on_player_joined(self, event: DomainEvent) -> None:
        try:
            server_id = event.server_id or ""
            name = event.payload.get("name", "")
            xuid = event.payload.get("xuid", "")
            if not server_id or not name or not xuid:
                return
            self._resolve(server_id, name, xuid)
        except Exception:  # noqa: BLE001 — defensivo, no rompe el bus
            logger.warning(
                "permission.allowlist_resolve_failed",
                extra={"name": name, "xuid": xuid, "event": event.type},
            )

    def _resolve(self, server_id: str, name: str, xuid: str) -> None:
        storage = self._storage.for_server(server_id)
        if not storage.exists(_ALLOWLIST_FILE):
            return
        raw = storage.read(_ALLOWLIST_FILE)
        try:
            entries: list[dict[str, Any]] = json.loads(raw)
        except json.JSONDecodeError:
            return
        updated = False
        for entry in entries:
            if entry.get("name") == name and not entry.get("xuid"):
                entry["xuid"] = xuid
                updated = True
        if updated:
            storage.write(
                _ALLOWLIST_FILE,
                json.dumps(entries, indent=2).encode("utf-8") + b"\n",
            )
            logger.info(
                "permission.allowlist_xuid_resolved",
                extra={"name": name, "xuid": xuid},
            )
