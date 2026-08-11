"""Handlers de eventos consumidos por el módulo Server (Blueprint §3.2).

El módulo reacciona a ``CONFIG.CHANGED``, ``WORLD.ACTIVATED`` y
``PERMISSION.ALLOWLIST_TOGGLED`` reaplicando la config deseada vía
``ApplyConfigUseCase``. ``SERVER.CONFIG_CHANGED`` (auto-recreate) no se vuelve
a rutear al propio Server para evitar bucles.
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
    """``WORLD.ACTIVATED`` → applyConfig (level-name + ajustes, §7.2).

    El payload de World **no** lleva ``config_rev`` (decisión §22): se
    reaplica la config deseada sin tocar la revisión aplicada. El ``name`` del
    mundo activado (directorio ``worlds/<name>``) se propaga como
    ``level_name`` para que el spec renderice ``LEVEL_NAME=<name>``; los
    ajustes opcionales del mundo (``seed``/``gamemode``/``difficulty``/
    ``view_distance``) se propagan como override de env
    (``LEVEL_SEED``/``GAMEMODE``/``DIFFICULTY``/``VIEW_DISTANCE``).
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
                environment=_world_environment(event),
                actor_id=event.actor_id,
            )
        )


class AllowlistToggledHandler:
    """``PERMISSION.ALLOWLIST_TOGGLED`` → applyConfig (ALLOW_LIST cambiado).

    El payload no lleva ``config_rev``: se reaplica la config deseada sin
    tocar la revisión aplicada. El ``enabled`` del toggle se propaga como
    ``allow_list`` para que el spec renderice ``ALLOW_LIST=<true/false>``.
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
                allow_list=_optional_allow_list(event),
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


def _optional_allow_list(event: DomainEvent) -> bool | None:
    """``enabled`` del toggle ALLOW_LIST como ``bool | None`` (``None`` = ausente)."""
    raw = event.payload.get("enabled")
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    return str(raw).lower() in ("true", "1", "yes")


# Claves del payload de ``WORLD.ACTIVATED`` → env que se inyecta al spec.
_WORLD_ENV_KEYS: tuple[tuple[str, str], ...] = (
    ("seed", "LEVEL_SEED"),
    ("gamemode", "GAMEMODE"),
    ("difficulty", "DIFFICULTY"),
    ("view_distance", "VIEW_DISTANCE"),
)


def _world_environment(event: DomainEvent) -> dict[str, str] | None:
    """Ajustes opcionales del mundo activado como override de env (``None`` = sin ajustes).

    Solo incluye claves presentes y no vacías; ``view_distance`` se proyecta a
    texto (los env del spec son ``str``). Si hay ``gamemode`` configurado se
    inyecta además ``FORCE_GAMEMODE=true``: en mundos existentes BDS usa el
    modo guardado en ``level.dat`` a menos que ``force-gamemode=true`` (el
    itzg image mapea ``FORCE_GAMEMODE`` → ``force-gamemode``).
    """
    environment: dict[str, str] = {}
    for payload_key, env_key in _WORLD_ENV_KEYS:
        raw = event.payload.get(payload_key)
        if raw is None or raw == "":
            continue
        environment[env_key] = str(raw)
    if "GAMEMODE" in environment:
        environment["FORCE_GAMEMODE"] = "true"
    return environment or None
