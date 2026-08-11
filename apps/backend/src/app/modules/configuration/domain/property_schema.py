"""Esquema de ``server.properties``: mapeo propiedad→env y validación.

Espejo de ``property-definitions.json`` (Blueprint §16.8): los valores
permitidos viven en el esquema, no en los adaptadores. El mapeo a variables de
entorno lo consume Server al renderizar el ``RuntimeSpec`` (Blueprint §5.4) a
través de ``DesiredConfig.environment``.
"""

from __future__ import annotations

_PROPERTY_TO_ENV: dict[str, str] = {
    "server-name": "SERVER_NAME",
    "max-players": "MAX_PLAYERS",
    "gamemode": "GAMEMODE",
    "difficulty": "DIFFICULTY",
    "level-name": "LEVEL_NAME",
    "level-seed": "LEVEL_SEED",
    "view-distance": "VIEW_DISTANCE",
}

_MAX_PLAYERS = 40


class PropertySchema:
    """Valida properties de ``server.properties`` y las proyecta a env."""

    def validate(self, properties: dict[str, str]) -> None:
        """Valida las properties antes de persistirlas (§16.8)."""
        for key, raw in properties.items():
            if key == "max-players" and int(raw) > _MAX_PLAYERS:
                raise ValueError(f"Valor inválido para {key}: {raw}")

    def to_environment(self, properties: dict[str, str]) -> dict[str, str]:
        """Proyecta properties conocidas a variables de entorno (mapeo §3.7)."""
        return {
            env_key: raw
            for raw_key, raw in properties.items()
            if (env_key := _PROPERTY_TO_ENV.get(raw_key)) is not None
        }
