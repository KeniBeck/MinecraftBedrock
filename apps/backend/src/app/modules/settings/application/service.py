"""Servicio de configuración (Fase H paso 19, Blueprint §3.13).

Implementa ``SettingsPort`` (lectura síncrona) y añade escritura/reset/reload
async con persistencia en ``SettingsRepositoryPort``. Resolución de cada clave:
DB (si está configurada) → ``EnvSettingsAdapter`` (fallback de entorno) →
default hardcodeado del catálogo → default del argumento.

Las escrituras validan el valor contra la definición del catálogo y se auditan
con la acción ``settings.update`` (audit log tamper-evident del paso 18).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.settings import SettingsPort, SettingsRepositoryPort
from app.kernel.time import TimeProviderPort
from app.modules.iam.application.ports import AuditEntry, AuditStorePort
from app.modules.settings.domain.defaults import (
    CATEGORIES,
    DEFAULT_VALUES,
    DEFINITIONS_BY_KEY,
    SETTING_DEFINITIONS,
    SettingDefinition,
)
from app.modules.settings.domain.errors import (
    SettingCategoryError,
    SettingNotFoundError,
    SettingValidationError,
)

SETTINGS_UPDATE_ACTION = "settings.update"
AUDIT_RESOURCE_TYPE = "settings"


class SettingsService:
    """Config global con persistencia y fallback a entorno/defaults."""

    def __init__(
        self,
        repository: SettingsRepositoryPort,
        fallback: SettingsPort,
        *,
        audit: AuditStorePort,
        ids: IdGeneratorPort,
        time: TimeProviderPort,
    ) -> None:
        self._repository = repository
        self._fallback = fallback
        self._audit = audit
        self._ids = ids
        self._time = time
        # Cache en memoria de los valores DB (cargados en ``reload``).
        self._cache: dict[str, Any] = {}

    # -- SettingsPort -------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._cache:
            return self._cache[key]
        env_value = self._fallback.get(key)
        if env_value is not None:
            return env_value
        return DEFAULT_VALUES.get(key, default)

    # -- Tipos --------------------------------------------------------------

    def get_int(self, key: str, default: int = 0) -> int:
        return int(self.get(key, default))

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def get_float(self, key: str, default: float = 0.0) -> float:
        return float(self.get(key, default))

    def get_path(self, key: str, default: str | Path = "/var/lib/bedrockpanel") -> Path:
        return Path(str(self.get(key, str(default))))

    # -- Escritura ----------------------------------------------------------

    async def reload(self) -> None:
        """Recarga la cache desde el repositorio (DB es la fuente principal).

        Tolerante a tabla ausente (migración sin aplicar): si el repositorio
        falla, la cache queda vacía y la resolución cae al fallback env/defaults.
        """
        try:
            self._cache = dict(await self._repository.get_all())
        except Exception:  # noqa: BLE001 — BBDD no migrada: fallback env/defaults
            self._cache = {}

    async def set(
        self,
        key: str,
        value: Any,
        *,
        updated_by: str,
        description: str | None = None,
        category: str | None = None,
    ) -> Any:
        definition = self._definition(key)
        category = category or definition.category
        validated = self.validate(definition, value)
        await self._repository.set(key, validated, category, description, updated_by)
        self._cache[key] = validated
        await self._audit_settings_update(
            key, validated, updated_by, description, previous=self._cache.get(key)
        )
        return validated

    async def set_many(
        self,
        values: dict[str, Any],
        *,
        updated_by: str,
        description: str | None = None,
    ) -> None:
        """Actualiza varios ajustes de forma atómica (transacción del repo)."""
        validated = {
            key: self.validate(self._definition(key), value) for key, value in values.items()
        }
        await self._repository.set_many(validated, description, updated_by)
        self._cache.update(validated)
        for key, value in validated.items():
            await self._audit_settings_update(key, value, updated_by, description)

    async def reset(self, key: str, *, updated_by: str) -> Any:
        """Elimina la sobreescritura y devuelve el valor por defecto."""
        definition = self._definition(key)
        await self._repository.delete(key)
        self._cache.pop(key, None)
        default = definition.default
        await self._audit_settings_update(key, default, updated_by, "reset a valor por defecto")
        return default

    # -- Lectura agregada ---------------------------------------------------

    async def get_all(self) -> list[dict[str, Any]]:
        """Devuelve todos los ajustes (catálogo + sobreescrituras) con metadata."""
        stored = await self._repository.list_full()
        by_key = {item["key"]: item for item in stored}
        result: list[dict[str, Any]] = []
        for definition in SETTING_DEFINITIONS:
            if definition.key in self._cache:
                value = self._cache[definition.key]
            elif definition.key in by_key:
                value = by_key[definition.key]["value"]
            else:
                env_value = self._fallback.get(definition.key)
                value = env_value if env_value is not None else definition.default
            result.append(
                {
                    "key": definition.key,
                    "value": value,
                    "category": definition.category,
                    "description": definition.description,
                    "type": definition.value_type,
                    "default": definition.default,
                }
            )
        return result

    async def get_category(self, category: str) -> list[dict[str, Any]]:
        if category not in CATEGORIES:
            raise SettingCategoryError(f"Categoría desconocida: {category}")
        all_settings = await self.get_all()
        return [item for item in all_settings if item["category"] == category]

    # -- Validación ---------------------------------------------------------

    def validate(self, definition: SettingDefinition, value: Any) -> Any:
        """Coerce/valida el valor contra la definición (tipos y rangos)."""
        value_type = definition.value_type
        try:
            if value_type == "int":
                coerced: object = int(value)
            elif value_type == "float":
                coerced = float(value)
            elif value_type == "bool":
                coerced = self._coerce_bool(value)
            elif value_type == "path" or value_type == "str":
                coerced = str(value)
            else:
                coerced = value
        except (TypeError, ValueError) as exc:
            raise SettingValidationError(
                f"Valor inválido para {definition.key}",
                context={"key": definition.key, "type": value_type, "value": value},
            ) from exc
        if isinstance(coerced, (int, float)):
            if definition.min_value is not None and coerced < definition.min_value:
                raise SettingValidationError(
                    f"Valor por debajo del mínimo para {definition.key}",
                    context={"key": definition.key, "min": definition.min_value},
                )
            if definition.max_value is not None and coerced > definition.max_value:
                raise SettingValidationError(
                    f"Valor por encima del máximo para {definition.key}",
                    context={"key": definition.key, "max": definition.max_value},
                )
        return coerced

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _definition(key: str) -> SettingDefinition:
        definition = DEFINITIONS_BY_KEY.get(key)
        if definition is None:
            raise SettingNotFoundError(f"Ajuste desconocido: {key}")
        return definition

    # -- Auditoría ----------------------------------------------------------

    async def _audit_settings_update(
        self,
        key: str,
        value: Any,
        updated_by: str,
        description: str | None,
        previous: Any = None,
    ) -> None:
        detail: dict[str, Any] = {"key": key, "value": value}
        if previous is not None:
            detail["previous"] = previous
        if description:
            detail["description"] = description
        await self._audit.record(
            AuditEntry(
                id=self._ids.new_id(),
                actor_id=updated_by,
                actor_type="user",
                action=SETTINGS_UPDATE_ACTION,
                result="success",
                created_at=self._time.now(),
                resource_type=AUDIT_RESOURCE_TYPE,
                resource_id=key,
                detail=detail,
            )
        )
