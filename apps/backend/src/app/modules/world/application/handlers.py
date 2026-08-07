"""Handlers de eventos consumidos por el módulo World (Blueprint §3.3).

World publica su propio ciclo de vida; solo consume ``SERVER.VERSION_CHANGED``
para **consistencia** (mismo patrón que ``OperatorChangedHandler`` de Player):
el payload se valida de forma defensiva sin lógica de negocio nueva. Persistir
la versión sobre el mundo activo (y validar formatos de versión) queda
pendiente de decisión (§22); el handler no corta el bus si el payload es
inválido.
"""

from __future__ import annotations

from app.kernel.events.event import DomainEvent

SERVER_VERSION_CHANGED_TOPIC = "server.version_changed"


class VersionChangedHandler:
    """``SERVER.VERSION_CHANGED`` — consistencia únicamente (decisión §22).

    Defensivo: requiere ``server_id`` y ``version`` en el payload; no hace nada
    más (no valida formatos de versión, no persiste aún).
    """

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id or event.payload.get("server_id")
        version = event.payload.get("version")
        if not server_id or not isinstance(version, str) or not version:
            return
