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
        await self._apply_config.execute(
            ApplyConfigCommand(
                server_id=server_id,
                config_rev=_optional_config_rev(event),
                actor_id=event.actor_id,
            )
        )


class WorldActivatedHandler:
    """``WORLD.ACTIVATED`` → applyConfig (level-name cambiado, §7.2).

    El payload de World **no** lleva ``config_rev`` (decisión §22): se
    reaplica la config deseada sin tocar la revisión aplicada. El ``name`` del
    mundo activado (directorio ``worlds/<name>``) se propaga como
    ``level_name`` para que el spec renderice ``LEVEL_NAME=<name>``.
    """

    def __init__(self, apply_config: ApplyConfigUseCase) -> None:
        self._apply_config = apply_config

    async def __call__(self, event: DomainEvent) -> None:
        server_id = event.server_id
        if not server_id:
            return
        await self._apply_config.execute(
            ApplyConfigCommand(
                server_id=server_id,
                config_rev=_optional_config_rev(event),
                level_name=_optional_level_name(event),
                actor_id=event.actor_id,
            )
        )


def _optional_config_rev(event: DomainEvent) -> int | None:
    """Revisión del payload como ``int | None`` (``None`` = no aplicable)."""
    raw = event.payload.get("config_rev")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _optional_level_name(event: DomainEvent) -> str | None:
    """``name`` del mundo activado (directorio en ``worlds/``) o ``None``."""
    raw = event.payload.get("name")
    if raw is None:
        return None
    return str(raw)
