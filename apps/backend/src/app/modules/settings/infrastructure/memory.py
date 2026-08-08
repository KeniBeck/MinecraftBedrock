"""Repositorio Settings en memoria para tests (Fase H paso 19).

Con ``overrides`` opcional para simular valores ya persistidos. ``set_many`` es
"atómico" en el sentido de que solo aplica si todas las claves son válidas.
"""

from __future__ import annotations

from typing import Any

from app.modules.settings.domain.defaults import DEFINITIONS_BY_KEY


class InMemorySettingsRepository:
    """``SettingsRepositoryPort`` con dicts por clave."""

    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        self._values: dict[str, Any] = dict(overrides or {})
        self._descriptions: dict[str, str | None] = {}
        self._categories: dict[str, str] = {}
        for key in self._values:
            definition = DEFINITIONS_BY_KEY.get(key)
            self._categories[key] = definition.category if definition else "system"

    async def get(self, key: str) -> Any | None:
        return self._values.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        category: str,
        description: str | None,
        updated_by: str,
    ) -> None:
        del updated_by
        self._values[key] = value
        self._categories[key] = category
        self._descriptions[key] = description

    async def set_many(
        self,
        values: dict[str, Any],
        description: str | None,
        updated_by: str,
    ) -> None:
        del updated_by
        for key, value in values.items():
            definition = DEFINITIONS_BY_KEY.get(key)
            category = definition.category if definition else "system"
            self._values[key] = value
            self._categories[key] = category
            self._descriptions[key] = description

    async def delete(self, key: str) -> None:
        self._values.pop(key, None)
        self._categories.pop(key, None)
        self._descriptions.pop(key, None)

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        return {key: self._values[key] for key in keys if key in self._values}

    async def list_by_category(self, category: str) -> dict[str, Any]:
        return {
            key: value
            for key, value in self._values.items()
            if self._categories.get(key) == category
        }

    async def get_all(self) -> dict[str, Any]:
        return dict(self._values)

    async def list_full(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for key, value in self._values.items():
            result.append(
                {
                    "key": key,
                    "value": value,
                    "category": self._categories.get(key, "system"),
                    "description": self._descriptions.get(key),
                }
            )
        result.sort(key=lambda item: item["key"])
        return result


def make_in_memory_settings_repository(
    overrides: dict[str, Any] | None = None,
) -> InMemorySettingsRepository:
    return InMemorySettingsRepository(overrides)
