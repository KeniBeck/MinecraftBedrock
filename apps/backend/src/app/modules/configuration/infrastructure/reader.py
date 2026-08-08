"""Adaptador de lectura de config Bedrock desde ``server.properties`` (Fase D).

Adaptador transicional: lee un fichero ``server.properties`` (o uno inyectado)
y lo mapea a env con el ``PropertySchema`` del dominio. Desde el paso 10 el
panel usa ``ConfigurationFacade`` (config deseada en ``ConfigProfile``, BBDD);
este adaptador se conserva para tooling/tests y como lectura de archivo.
"""

from __future__ import annotations

from pathlib import Path

from app.kernel.ports.settings import SettingsPort
from app.modules.configuration.domain.property_schema import PropertySchema
from app.modules.server.application.ports import DesiredConfig


class BedrockConfigurationReader:
    """Lee server.properties y lo mapea a env para el runtime Bedrock."""

    def __init__(
        self,
        settings: SettingsPort,
        *,
        properties_path: str | Path | None = None,
        schema: PropertySchema | None = None,
    ) -> None:
        self._settings = settings
        self._schema = schema or PropertySchema()
        self._properties_path = Path(properties_path) if properties_path is not None else None

    async def desired_config(self, server_id: str) -> DesiredConfig:
        del server_id
        properties = self._load_properties()
        self._schema.validate(properties)
        return DesiredConfig(
            version=str(
                self._settings.get(
                    "defaults.version", self._settings.get("server.default_version", "LATEST")
                )
            ),
            environment=self._schema.to_environment(properties),
            config_rev=0,
        )

    def _load_properties(self) -> dict[str, str]:
        if self._properties_path is not None:
            path = self._properties_path
        else:
            base = self._settings.get("storage.base_path", "/var/lib/bedrockpanel")
            path = Path(base) / "server.properties"

        if not path.exists():
            return {}

        parsed: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            parsed[key.strip()] = value.strip()
        return parsed
