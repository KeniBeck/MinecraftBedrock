"""Handlers de eventos consumidos por el módulo Server (Blueprint §3.2).

El módulo reacciona a ``CONFIG.CHANGED`` y ``WORLD.ACTIVATED`` reaplicando la
config deseada vía ``ApplyConfigUseCase``. ``SERVER.CONFIG_CHANGED`` (auto-
recreate) no se vuelve a rutear al propio Server para evitar bucles.
"""

from __future__ import annotations

from app.kernel.events.event import DomainEvent
from app.modules.server.application.commands import ApplyConfigCommand
from app.modules.server.application.use_cases import ApplyConfigUseCase


class ConfigChangedHandler:
    """``CONFIG.CHANGED`` → applyConfig (Blueprint §3.2, §16.8)."""

    def __init__(self, apply_config: ApplyConfigUseCase) -> None:
        self._apply_config = apply_config

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id or event.payload.get("server_id")
        if not server_id:
            return
        config_rev = int(event.payload.get("config_rev", 0))
        await self._apply_config.execute(
            ApplyConfigCommand(
                server_id=server_id,
                config_rev=config_rev,
                actor_id=event.actor_id,
            )
        )


class WorldActivatedHandler:
    """``WORLD.ACTIVATED`` → applyConfig (level-name cambiado, §7.2)."""

    def __init__(self, apply_config: ApplyConfigUseCase) -> None:
        self._apply_config = apply_config

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id
        if not server_id:
            return
        config_rev = int(event.payload.get("config_rev", 0))
        await self._apply_config.execute(
            ApplyConfigCommand(
                server_id=server_id,
                config_rev=config_rev,
                actor_id=event.actor_id,
            )
        )
