"""Tests del ``SettingsService`` (Fase H paso 19).

Verifica la resolución DB → env → default, los getters tipados, la validación,
la auditoría y el reset.
"""

from __future__ import annotations

import pytest

from app.kernel.ports.settings import SettingsPort
from app.modules.iam.infrastructure.memory import InMemoryAuditStore
from app.modules.settings.application.service import SettingsService
from app.modules.settings.domain.defaults import CATEGORIES, DEFAULT_VALUES
from app.modules.settings.domain.errors import (
    SettingCategoryError,
    SettingNotFoundError,
    SettingValidationError,
)
from app.modules.settings.infrastructure.memory import InMemorySettingsRepository
from tests.conftest import FakeSettings, FakeTime, SequenceIds

NOW = FakeTime().now()


class FakeEnvSettings:
    """``SettingsPort`` que simula el fallback de entorno."""

    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def get(self, key: str, default: object = None) -> object:
        return self._values.get(key, default)


async def build(
    *,
    overrides: dict[str, object] | None = None,
    env: dict[str, object] | None = None,
) -> SettingsService:
    repository = InMemorySettingsRepository(overrides)
    audit = InMemoryAuditStore()
    service = SettingsService(
        repository,
        FakeEnvSettings(env or {}),
        audit=audit,
        ids=SequenceIds("a1"),
        time=FakeTime(NOW),
    )
    await service.reload()
    return service


class TestResolucion:
    async def test_default_catalogo_cuando_no_hay_valor(self) -> None:
        service = await build()
        assert service.get("limits.max_backups_per_server") == 10

    async def test_env_supera_al_default_catalogo(self) -> None:
        service = await build(env={"limits.max_backups_per_server": 99})
        assert service.get("limits.max_backups_per_server") == 99

    async def test_db_supera_al_env(self) -> None:
        service = await build(overrides={"limits.max_backups_per_server": 42})
        assert service.get("limits.max_backups_per_server") == 42

    async def test_default_del_argumento_como_fallback_final(self) -> None:
        service = await build()
        assert service.get("clave.inexistente", 7) == 7

    async def test_set_actualiza_y_reload_refresca(self) -> None:
        service = await build()
        await service.set("system.log_level", "DEBUG", updated_by="u1")
        assert service.get("system.log_level") == "DEBUG"
        await service.reload()
        assert service.get("system.log_level") == "DEBUG"


class TestTipos:
    async def test_get_int(self) -> None:
        service = await build(overrides={"limits.default_ram_mb": "4096"})
        assert service.get_int("limits.default_ram_mb") == 4096

    async def test_get_float(self) -> None:
        service = await build(overrides={"limits.default_cpu_cores": "4.5"})
        assert service.get_float("limits.default_cpu_cores") == 4.5

    async def test_get_bool_texto(self) -> None:
        service = await build(overrides={"system.maintenance_mode": "true"})
        assert service.get_bool("system.maintenance_mode") is True

    async def test_get_bool_booleano(self) -> None:
        service = await build(overrides={"system.maintenance_mode": False})
        assert service.get_bool("system.maintenance_mode") is False

    async def test_get_path(self) -> None:
        service = await build(overrides={"storage.base_path": "/tmp/data"})
        assert str(service.get_path("storage.base_path")) == "/tmp/data"


class TestValidacion:
    async def test_set_valida_tipo_int(self) -> None:
        service = await build()
        with pytest.raises(SettingValidationError):
            await service.set("limits.max_backups_per_server", "no-un-numero", updated_by="u1")

    async def test_set_valida_coercion_bool(self) -> None:
        service = await build()
        value = await service.set("system.maintenance_mode", "yes", updated_by="u1")
        assert value is True

    async def test_set_clave_desconocida_lanza(self) -> None:
        service = await build()
        with pytest.raises(SettingNotFoundError):
            await service.set("clave.inventada", 1, updated_by="u1")


class TestAuditoria:
    async def test_set_registra_auditoria(self) -> None:
        repository = InMemorySettingsRepository()
        audit = InMemoryAuditStore()
        service = SettingsService(
            repository,
            FakeEnvSettings({}),
            audit=audit,
            ids=SequenceIds("a1"),
            time=FakeTime(NOW),
        )
        await service.set("system.log_level", "DEBUG", updated_by="u1")
        assert len(audit.entries) == 1
        entry = audit.entries[0]
        assert entry.action == "settings.update"
        assert entry.resource_id == "system.log_level"
        assert entry.detail["value"] == "DEBUG"

    async def test_reset_registra_auditoria(self) -> None:
        repository = InMemorySettingsRepository()
        audit = InMemoryAuditStore()
        service = SettingsService(
            repository,
            FakeEnvSettings({}),
            audit=audit,
            ids=SequenceIds("a1"),
            time=FakeTime(NOW),
        )
        await service.reset("system.log_level", updated_by="u1")
        assert audit.entries[0].action == "settings.update"
        assert audit.entries[0].detail["value"] == "INFO"


class TestAgregados:
    async def test_get_all_incluye_catalogo_y_sobreescrituras(self) -> None:
        service = await build(overrides={"system.maintenance_mode": True})
        items = await service.get_all()
        keys = {item["key"] for item in items}
        assert keys == set(DEFAULT_VALUES)
        maintenance = next(i for i in items if i["key"] == "system.maintenance_mode")
        assert maintenance["value"] is True

    async def test_get_category_filtra(self) -> None:
        service = await build()
        storage = await service.get_category("storage")
        assert all(item["category"] == "storage" for item in storage)
        assert {item["key"] for item in storage} == {
            "storage.base_path",
            "storage.backup_path",
            "storage.template_path",
        }

    async def test_get_category_invalida_lanza(self) -> None:
        service = await build()
        with pytest.raises(SettingCategoryError):
            await service.get_category("nope")

    async def test_categorias_catalogo(self) -> None:
        assert CATEGORIES == ("storage", "limits", "defaults", "system")


async def test_settings_port_estructural() -> None:
    service = await build()
    port: SettingsPort = service
    assert port.get("limits.max_backups_per_server") == 10


def test_fake_settings_compatible() -> None:
    fake = FakeSettings({"a": 1})
    assert fake.get("a") == 1
    assert fake.get("b", 2) == 2
