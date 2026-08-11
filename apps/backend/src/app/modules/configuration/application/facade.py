"""Facade pública del módulo Configuration (Blueprint §3.7, §5.4).

Expone la config deseada en modo lectura (implementa el protocolo
``ConfigurationReader`` que consume Server) y la actualización de properties:
valida → persiste ``ConfigProfile`` (revisión) → publica ``CONFIG.CHANGED``.
La aplicación de la config la hace Server (unidireccional, §3.2).
"""

from __future__ import annotations

from app.kernel.events.bus import EventBusPort
from app.kernel.ports.settings import SettingsPort
from app.kernel.time import TimeProviderPort
from app.modules.configuration.domain.config_profile import ConfigChange, ConfigProfile
from app.modules.configuration.domain.events import config_changed
from app.modules.configuration.domain.property_schema import PropertySchema
from app.modules.configuration.domain.repository import ConfigurationRepositoryPort
from app.modules.server.application.ports import DesiredConfig


class ConfigurationFacade:
    """Puerta de entrada del módulo Configuration (validate → persist → event)."""

    def __init__(
        self,
        repository: ConfigurationRepositoryPort,
        schema: PropertySchema,
        bus: EventBusPort,
        settings: SettingsPort,
        time: TimeProviderPort,
    ) -> None:
        self._repository = repository
        self._schema = schema
        self._bus = bus
        self._settings = settings
        self._time = time

    async def desired_config(self, server_id: str) -> DesiredConfig:
        """Vista de solo lectura para Server (protocolo ``ConfigurationReader``).

        Sin perfil (servidor recién creado, sin plantilla ni config del
        usuario) se siembra el ``level-name`` por defecto (``defaults.level_name``,
        por defecto ``Mi Mundo 1``): así BDS genera el mundo inicial con ese
        nombre en el primer arranque. Con perfil, solo se proyectan las
        properties guardadas (si el perfil no define ``level-name``, BDS usa su
        default — la decisión del usuario gana).
        """
        profile = await self._repository.get_profile(server_id)
        if profile is None:
            return DesiredConfig(
                version=str(
                    self._settings.get(
                        "defaults.version", self._settings.get("server.default_version", "LATEST")
                    )
                ),
                environment={"LEVEL_NAME": self._default_level_name()},
                config_rev=0,
            )
        return DesiredConfig(
            version=profile.version,
            environment=self._schema.to_environment(profile.properties),
            config_rev=profile.config_rev,
        )

    def _default_level_name(self) -> str:
        return str(self._settings.get("defaults.level_name", "Mi Mundo 1"))

    async def get_profile(self, server_id: str) -> ConfigProfile | None:
        return await self._repository.get_profile(server_id)

    async def update_properties(
        self,
        server_id: str,
        properties: dict[str, str],
        *,
        actor_id: str | None = None,
    ) -> ConfigProfile:
        """Valida, persiste (revisión+1) y publica ``CONFIG.CHANGED`` si cambió."""
        self._schema.validate(properties)
        now = self._time.now()
        profile = await self._repository.get_profile(server_id)
        if profile is None:
            profile = ConfigProfile(
                server_id=server_id,
                properties={},
                version=str(
                    self._settings.get(
                        "defaults.version", self._settings.get("server.default_version", "LATEST")
                    )
                ),
                config_rev=0,
                created_at=now,
                updated_at=now,
            )
        if profile.properties == properties:
            return profile

        next_rev = profile.config_rev + 1
        updated = ConfigProfile(
            server_id=server_id,
            properties=dict(properties),
            version=profile.version,
            config_rev=next_rev,
            created_at=profile.created_at,
            updated_at=now,
            applied=profile.applied,
            applied_at=profile.applied_at,
        )
        await self._repository.save_profile(updated)
        await self._repository.append_change(
            ConfigChange(
                server_id=server_id,
                config_rev=next_rev,
                properties=dict(properties),
                version=updated.version,
                changed_at=now,
                actor_id=actor_id,
            )
        )
        await self._bus.publish(config_changed(server_id, next_rev, actor_id=actor_id))
        return updated
