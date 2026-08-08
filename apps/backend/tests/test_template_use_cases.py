"""Tests del módulo Template (Fase G paso 16, hallazgo B5).

Cubre el ciclo de vida síncrono de las plantillas ``.mctemplate``: capturar el
estado de un servidor (mundo + config), aplicar (reproducir) a un destino con
validación de ``level.dat``, listar/consultar y eliminar. Se usan dobles
inyectados con el mismo criterio que World: storage local sobre ``tmp_path``,
repositorio en memoria, store del artefacto sobre disco y un gateway de config
mínimo.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.infrastructure.storage.local import LocalServerStorage
from app.kernel.errors import StorageError
from app.modules.configuration.domain.config_profile import ConfigProfile
from app.modules.template.application.commands import (
    ApplyTemplateCommand,
    CaptureTemplateCommand,
    DeleteTemplateCommand,
)
from app.modules.template.application.facade import TemplateFacade
from app.modules.template.application.use_cases import TemplateDeps
from app.modules.template.domain.errors import (
    TemplateCorruptError,
    TemplateNotFoundError,
    TemplateValidationError,
    TemplateWorldExistsError,
)
from app.modules.template.infrastructure.archive import (
    build_template_archive,
    open_template_archive,
)
from app.modules.template.infrastructure.memory import InMemoryTemplateRepository
from tests.conftest import FakeSettings, SequenceIds

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SERVER_ID = "srv-1"


class Clock:
    """``TimeProviderPort`` con hora fija."""

    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class TmpStorageResolver:
    """``ServerStorageResolver`` sobre ``tmp_path`` (un subdir por servidor)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._cache: dict[str, LocalServerStorage] = {}

    def for_server(self, server_id: str) -> LocalServerStorage:
        storage = self._cache.get(server_id)
        if storage is None:
            storage = LocalServerStorage(self._root / server_id)
            self._cache[server_id] = storage
        return storage


class FakeWorldGateway:
    """``WorldGateway`` en memoria: devuelve el mundo activo de un servidor."""

    def __init__(self) -> None:
        self.active: dict[str, str] = {}

    def seed(self, server_id: str, world_name: str) -> None:
        self.active[server_id] = world_name

    async def active_world(self, server_id: str) -> str | None:
        return self.active.get(server_id)


class FakeTemplateConfig:
    """``ConfigurationGateway`` en memoria con properties por servidor."""

    def __init__(self, profile: dict[str, str] | None = None) -> None:
        self.properties: dict[str, dict[str, str]] = {}
        self.updates: list[tuple[str, dict[str, str]]] = []
        if profile is not None:
            self.properties[SERVER_ID] = profile

    def seed(self, server_id: str, properties: dict[str, str]) -> None:
        self.properties[server_id] = dict(properties)

    async def get_profile(self, server_id: str) -> ConfigProfile | None:
        properties = self.properties.get(server_id)
        if properties is None:
            return None
        return ConfigProfile(
            server_id=server_id,
            properties=dict(properties),
            version="1.20.0",
            config_rev=1,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    async def update_properties(
        self,
        server_id: str,
        properties: dict[str, str],
        *,
        actor_id: str | None = None,
    ) -> ConfigProfile:
        del actor_id
        self.properties[server_id] = dict(properties)
        self.updates.append((server_id, dict(properties)))
        return ConfigProfile(
            server_id=server_id,
            properties=dict(properties),
            version="1.20.0",
            config_rev=2,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


class InMemoryArchiveStore:
    """``TemplateArchiveWriter`` en memoria."""

    def __init__(self) -> None:
        self._artifacts: dict[str, bytes] = {}

    def write(self, template_id: str, data: bytes) -> int:
        self._artifacts[template_id] = data
        return len(data)

    def read(self, template_id: str) -> bytes:
        if template_id not in self._artifacts:
            raise StorageError(
                "El artefacto no existe",
                context={"template_id": template_id},
            )
        return self._artifacts[template_id]

    def exists(self, template_id: str) -> bool:
        return template_id in self._artifacts

    def remove(self, template_id: str) -> None:
        self._artifacts.pop(template_id, None)


class Fixture:
    """Deps del módulo Template con dobles inyectados."""

    def __init__(
        self,
        storage_root: Path,
        *,
        properties: dict[str, str] | None = None,
    ) -> None:
        props = dict(properties or {"level-name": "Alpha", "gamemode": "survival"})
        self.clock = Clock()
        self.repository = InMemoryTemplateRepository()
        self.config = FakeTemplateConfig(props)
        self.world = FakeWorldGateway()
        self.world.seed(SERVER_ID, props.get("level-name") or "Alpha")
        self.archive = InMemoryArchiveStore()
        self.deps = TemplateDeps(
            repository=self.repository,
            storage=TmpStorageResolver(storage_root),
            world=self.world,
            config=self.config,
            archive=self.archive,
            ids=SequenceIds("tpl-1", "tpl-2", "tpl-3"),
            time=self.clock,
            settings=FakeSettings({"server.default_version": "LATEST"}),
        )
        self.facade = TemplateFacade(self.deps)
        self.storage = self.deps.storage.for_server(SERVER_ID)

    def seed_world(self, name: str = "Alpha") -> None:
        self.storage.write(f"worlds/{name}/level.dat", b"\x0a\x00\x00")
        self.storage.write(f"worlds/{name}/levelname.txt", name.encode("utf-8"))


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    return tmp_path / "storage"


# -- archive -------------------------------------------------------------


def test_build_open_roundtrip() -> None:
    world = make_world_zip("Alpha")
    archive = build_template_archive(
        name="Mi Plantilla",
        version="1.20.0",
        origin_world="Alpha",
        properties={"gamemode": "survival"},
        world_bytes=world,
    )
    parsed = open_template_archive(archive)
    assert parsed.name == "Mi Plantilla"
    assert parsed.version == "1.20.0"
    assert parsed.origin_world == "Alpha"
    assert parsed.world_name == "Alpha"
    assert parsed.properties == {"gamemode": "survival"}
    assert parsed.world_bytes == world


def test_open_rechaza_miembros_inesperados() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", b"{}")
    with pytest.raises(TemplateCorruptError):
        open_template_archive(buf.getvalue())


# -- capturar ------------------------------------------------------------


async def test_capturar_crea_metadata_y_artefacto(storage_root: Path) -> None:
    fx = Fixture(storage_root, properties={"level-name": "Alpha", "gamemode": "survival"})
    fx.seed_world("Alpha")

    view = await fx.facade.capture(
        CaptureTemplateCommand(server_id=SERVER_ID, name="Supervivencia", actor_id="u1")
    )

    assert view.id == "tpl-1"
    assert view.name == "Supervivencia"
    assert view.version == "1.20.0"
    assert view.origin_server_id == SERVER_ID
    assert view.origin_world == "Alpha"
    assert view.size_bytes > 0
    assert fx.archive.exists("tpl-1")
    stored = await fx.repository.get("tpl-1")
    assert stored is not None and stored.name == "Supervivencia"


async def test_capturar_nombre_duplicado_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    await fx.facade.capture(
        CaptureTemplateCommand(server_id=SERVER_ID, name="Super", actor_id="u1")
    )

    with pytest.raises(TemplateValidationError):
        await fx.facade.capture(
            CaptureTemplateCommand(server_id=SERVER_ID, name="Super", actor_id="u1")
        )


async def test_capturar_sin_world_activo_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root, properties={"gamemode": "survival"})
    fx.seed_world("Alpha")
    fx.world.active.clear()

    with pytest.raises(TemplateValidationError):
        await fx.facade.capture(
            CaptureTemplateCommand(server_id=SERVER_ID, name="SinWorld", actor_id="u1")
        )


async def test_capturar_mundo_activo_viene_de_world_no_de_config(storage_root: Path) -> None:
    fx = Fixture(storage_root, properties={"gamemode": "survival"})
    fx.seed_world("Alpha")
    fx.world.seed(SERVER_ID, "Alpha")

    view = await fx.facade.capture(
        CaptureTemplateCommand(server_id=SERVER_ID, name="DesdeWorld", actor_id="u1")
    )

    assert view.origin_world == "Alpha"
    assert fx.archive.exists("tpl-1")


async def test_capturar_world_inexistente_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root, properties={"level-name": "Phantom", "gamemode": "survival"})

    with pytest.raises(TemplateValidationError):
        await fx.facade.capture(
            CaptureTemplateCommand(server_id=SERVER_ID, name="Fantasma", actor_id="u1")
        )


@pytest.mark.parametrize(
    "name",
    ["", "  ", ".hidden", "..", "a/b", "a\\b", "x" * 256],
)
async def test_capturar_nombre_invalido_fracasa(storage_root: Path, name: str) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")

    with pytest.raises(TemplateValidationError):
        await fx.facade.capture(
            CaptureTemplateCommand(server_id=SERVER_ID, name=name, actor_id="u1")
        )


# -- aplicar (reproducir) -------------------------------------------------


async def test_aplicar_restaura_mundo_y_actualiza_config(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    view = await fx.facade.capture(
        CaptureTemplateCommand(server_id=SERVER_ID, name="Origen", actor_id="u1")
    )

    result = await fx.facade.apply(
        ApplyTemplateCommand(
            server_id=SERVER_ID, template_id=view.id, world_name="Cli", actor_id="u1"
        )
    )

    assert result.world_name == "Cli"
    assert result.template.name == "Origen"
    assert fx.storage.exists("worlds/Cli/level.dat")
    updated = fx.config.properties[SERVER_ID]
    assert updated["level-name"] == "Cli"
    assert updated["gamemode"] == "survival"


async def test_aplicar_world_destino_ocupado_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    view = await fx.facade.capture(
        CaptureTemplateCommand(server_id=SERVER_ID, name="Origen", actor_id="u1")
    )
    fx.seed_world("Ocupado")

    with pytest.raises(TemplateWorldExistsError):
        await fx.facade.apply(
            ApplyTemplateCommand(
                server_id=SERVER_ID, template_id=view.id, world_name="Ocupado", actor_id="u1"
            )
        )


async def test_aplicar_template_inexistente_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)

    with pytest.raises(TemplateNotFoundError):
        await fx.facade.apply(
            ApplyTemplateCommand(
                server_id=SERVER_ID, template_id="nope", world_name="X", actor_id="u1"
            )
        )


async def test_aplicar_mundo_corrupto_sin_level_dat_limpia(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    view = await fx.facade.capture(
        CaptureTemplateCommand(server_id=SERVER_ID, name="Origen", actor_id="u1")
    )
    broken_world = io.BytesIO()
    with zipfile.ZipFile(broken_world, "w") as zf:
        zf.writestr("basura.txt", b"no level.dat")
    fx.archive.write(
        view.id,
        build_template_archive(
            name="Origen",
            version="1.20.0",
            origin_world="Alpha",
            properties={"level-name": "Alpha"},
            world_bytes=broken_world.getvalue(),
        ),
    )

    with pytest.raises(TemplateCorruptError):
        await fx.facade.apply(
            ApplyTemplateCommand(
                server_id=SERVER_ID, template_id=view.id, world_name="Rot", actor_id="u1"
            )
        )

    assert not fx.storage.exists("worlds/Rot")


# -- listar / consultar / borrar ------------------------------------------


async def test_listar_devuelve_ordenadas(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    await fx.facade.capture(CaptureTemplateCommand(server_id=SERVER_ID, name="B", actor_id="u1"))
    await fx.facade.capture(CaptureTemplateCommand(server_id=SERVER_ID, name="A", actor_id="u2"))

    views = await fx.facade.list_templates()

    assert [v.name for v in views] == ["B", "A"]


async def test_obtener_por_id(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    view = await fx.facade.capture(
        CaptureTemplateCommand(server_id=SERVER_ID, name="Unica", actor_id="u1")
    )

    assert await fx.facade.get_template(view.id) is not None
    assert await fx.facade.get_template("no-existe") is None


async def test_borrar_quita_metadata_y_artefacto(storage_root: Path) -> None:
    fx = Fixture(storage_root)
    fx.seed_world("Alpha")
    view = await fx.facade.capture(
        CaptureTemplateCommand(server_id=SERVER_ID, name="Descartable", actor_id="u1")
    )

    await fx.facade.delete(DeleteTemplateCommand(template_id=view.id, actor_id="u1"))

    assert not fx.archive.exists(view.id)
    assert await fx.facade.get_template(view.id) is None


async def test_borrar_template_inexistente_fracasa(storage_root: Path) -> None:
    fx = Fixture(storage_root)

    with pytest.raises(TemplateNotFoundError):
        await fx.facade.delete(DeleteTemplateCommand(template_id="nope", actor_id="u1"))


# -- helpers ---------------------------------------------------------------


def make_world_zip(name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("level.dat", b"\x0a\x00\x00")
        zf.writestr("levelname.txt", name.encode("utf-8"))
    return buf.getvalue()
