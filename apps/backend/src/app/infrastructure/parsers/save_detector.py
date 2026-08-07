"""Parser declarativo: detección de líneas de guardado → ``WORLD.SAVED`` (§7.3).

Consumidor externo de ``CONSOLE.OUTPUT``: reconoce el patrón de línea que
indica que BDS terminó un guardado y publica ``WORLD.SAVED`` sin interpretar
semántica de negocio (Backup/Monitoring resuelven el significado). Vive fuera
del núcleo de Console, en ``infrastructure/parsers``, como marca el Blueprint.
"""

from __future__ import annotations

import re

from app.kernel.events.bus import EventBusPort
from app.kernel.events.event import DomainEvent
from app.modules.console.domain.events import world_saved

_SAVE_COMPLETION = re.compile(
    r"save complete|saved the game|autosave (complete|finished)",
    re.IGNORECASE,
)
_SAVE_COMMAND = re.compile(r"save hold|save resume", re.IGNORECASE)


class SaveDetector:
    """Parser declarativo: líneas de guardado completado → ``WORLD.SAVED``."""

    def __init__(self, bus: EventBusPort) -> None:
        self._bus = bus

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id
        if not server_id:
            return
        line = str(event.payload.get("line", ""))
        if _is_save_completion(line):
            await self._bus.publish(world_saved(server_id, line))


def _is_save_completion(line: str) -> bool:
    """True si la línea indica guardado completado (no comandos hold/resume)."""
    if _SAVE_COMMAND.search(line):
        return False
    return bool(_SAVE_COMPLETION.search(line))
