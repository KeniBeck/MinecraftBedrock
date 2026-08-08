"""Catálogo de ajustes del panel (Fase H paso 19, TDD §15.7).

Categorías: ``storage``, ``limits``, ``defaults`` y ``system``. Cada clave tiene
valor por defecto, categoría y descripción. El catálogo es la fuente para la
siembra de la migración y el fallback hardcodeado de ``SettingsService``.
"""

from __future__ import annotations

from dataclasses import dataclass

CATEGORY_STORAGE = "storage"
CATEGORY_LIMITS = "limits"
CATEGORY_DEFAULTS = "defaults"
CATEGORY_SYSTEM = "system"

CATEGORIES = (CATEGORY_STORAGE, CATEGORY_LIMITS, CATEGORY_DEFAULTS, CATEGORY_SYSTEM)


@dataclass(frozen=True, slots=True)
class SettingDefinition:
    """Definición de un ajuste del catálogo."""

    key: str
    default: object
    category: str
    description: str
    value_type: str = "any"
    min_value: int | float | None = None
    max_value: int | float | None = None


# (key, default, category, description, value_type)
_SETTING_TUPPLES: tuple[tuple[str, object, str, str, str], ...] = (
    # storage
    (
        "storage.base_path",
        "/var/lib/bedrockpanel/data",
        CATEGORY_STORAGE,
        "Ruta base para los datos de los servidores",
        "path",
    ),
    (
        "storage.backup_path",
        "/var/lib/bedrockpanel/backups",
        CATEGORY_STORAGE,
        "Ruta base para los backups",
        "path",
    ),
    (
        "storage.template_path",
        "/var/lib/bedrockpanel/templates",
        CATEGORY_STORAGE,
        "Ruta base para las plantillas",
        "path",
    ),
    # limits
    (
        "limits.max_servers",
        0,
        CATEGORY_LIMITS,
        "Número máximo de servidores por usuario (0 = ilimitado)",
        "int",
    ),
    (
        "limits.max_backups_per_server",
        10,
        CATEGORY_LIMITS,
        "Número máximo de backups por servidor",
        "int",
    ),
    (
        "limits.max_world_size_mb",
        2048,
        CATEGORY_LIMITS,
        "Tamaño máximo de mundo importado (MB)",
        "int",
    ),
    (
        "limits.default_cpu_cores",
        2.0,
        CATEGORY_LIMITS,
        "CPU por defecto para nuevos servidores",
        "float",
    ),
    (
        "limits.default_ram_mb",
        2048,
        CATEGORY_LIMITS,
        "RAM por defecto para nuevos servidores (MB)",
        "int",
    ),
    (
        "limits.default_disk_gb",
        10,
        CATEGORY_LIMITS,
        "Disco por defecto para nuevos servidores (GB)",
        "int",
    ),
    # defaults
    (
        "defaults.image",
        "itzg/minecraft-bedrock-server",
        CATEGORY_DEFAULTS,
        "Imagen Docker por defecto",
        "str",
    ),
    (
        "defaults.tag",
        "latest",
        CATEGORY_DEFAULTS,
        "Tag de la imagen Docker por defecto",
        "str",
    ),
    (
        "defaults.version",
        "LATEST",
        CATEGORY_DEFAULTS,
        "Versión BDS por defecto",
        "str",
    ),
    (
        "defaults.port_pool_start",
        19132,
        CATEGORY_DEFAULTS,
        "Inicio del pool de puertos de juego",
        "int",
    ),
    (
        "defaults.port_pool_end",
        19181,
        CATEGORY_DEFAULTS,
        "Fin del pool de puertos de juego",
        "int",
    ),
    (
        "defaults.timezone",
        "Etc/UTC",
        CATEGORY_DEFAULTS,
        "Zona horaria por defecto",
        "str",
    ),
    # system
    (
        "system.maintenance_mode",
        False,
        CATEGORY_SYSTEM,
        "Panel en mantenimiento (bloquea operaciones)",
        "bool",
    ),
    (
        "system.log_level",
        "INFO",
        CATEGORY_SYSTEM,
        "Nivel de logs por defecto",
        "str",
    ),
    (
        "system.audit_retention_days",
        90,
        CATEGORY_SYSTEM,
        "Días de retención del audit log",
        "int",
    ),
)

SETTING_DEFINITIONS: tuple[SettingDefinition, ...] = tuple(
    SettingDefinition(
        key=key,
        default=default,
        category=category,
        description=description,
        value_type=value_type,
    )
    for key, default, category, description, value_type in _SETTING_TUPPLES
)

# Defaults hardcodeados (fallback final de resolución).
DEFAULT_VALUES: dict[str, object] = {d.key: d.default for d in SETTING_DEFINITIONS}

# Definiciones por clave.
DEFINITIONS_BY_KEY: dict[str, SettingDefinition] = {d.key: d for d in SETTING_DEFINITIONS}
