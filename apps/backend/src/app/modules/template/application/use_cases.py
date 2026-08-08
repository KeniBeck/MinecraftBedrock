"""Use cases del módulo Template (Blueprint §3.11, hallazgo B5).

El módulo es **síncrono** (request/response): capturar, aplicar, listar y
eliminar usan ``ServerStorageResolver`` (mundo) + ``ConfigurationGateway``
(config) + ``TemplateArchiveWriter`` (artefacto). No publica ni consume eventos.

Capturar: empaqueta el estado actual (mundo activo vía
``ServerStoragePort.world_snapshot`` + config deseada) en un ``.mctemplate``.
Aplicar (reproducir): extrae el artefacto, restaura el mundo en el destino
(``write_snapshot`` validando ``level.dat``) y reaplica la config capturada
(ajustando ``level-name`` al nuevo mundo).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.settings import SettingsPort
from app.kernel.ports.storage import ServerStoragePort
from app.kernel.time import TimeProviderPort
from app.modules.configuration.domain.config_profile import ConfigProfile
from app.modules.template.application.commands import (
    ApplyTemplateCommand,
    CaptureTemplateCommand,
    DeleteTemplateCommand,
)
from app.modules.template.application.ports import (
    ConfigurationGateway,
    ServerStorageResolver,
    TemplateArchiveWriter,
    WorldGateway,
)
from app.modules.template.application.results import (
    ApplyTemplateResult,
    TemplateView,
    template_to_view,
)
from app.modules.template.domain.errors import (
    TemplateCorruptError,
    TemplateNotFoundError,
    TemplateValidationError,
    TemplateWorldExistsError,
)
from app.modules.template.domain.repository import TemplateRepositoryPort
from app.modules.template.domain.template import Template
from app.modules.template.infrastructure.archive import (
    build_template_archive,
    open_template_archive,
)

_LEVEL_DAT = "level.dat"


@dataclass(slots=True)
class TemplateDeps:
    """Dependencias comunes de los use cases del módulo Template."""

    repository: TemplateRepositoryPort
    storage: ServerStorageResolver
    world: WorldGateway
    config: ConfigurationGateway
    archive: TemplateArchiveWriter
    ids: IdGeneratorPort
    time: TimeProviderPort
    settings: SettingsPort


class CaptureTemplateUseCase:
    """Captura el estado actual de un servidor como plantilla ``.mctemplate``."""

    def __init__(self, deps: TemplateDeps) -> None:
        self._deps = deps

    async def capture(self, cmd: CaptureTemplateCommand) -> TemplateView:
        deps = self._deps
        name = _clean_name(cmd.name)
        if not cmd.server_id:
            raise TemplateValidationError(
                "server_id requerido",
                context={"server_id": cmd.server_id},
            )
        if await deps.repository.get_by_name(name) is not None:
            raise TemplateValidationError(
                "Ya existe una plantilla con ese nombre",
                context={"name": name},
            )

        profile = await deps.config.get_profile(cmd.server_id)
        version, properties = _profile_config(deps, profile)
        origin_world = await deps.world.active_world(cmd.server_id)
        if not origin_world:
            raise TemplateValidationError(
                "No se determinó el mundo activo del servidor",
                context={"server_id": cmd.server_id},
            )

        storage = deps.storage.for_server(cmd.server_id)
        if not storage.exists(f"worlds/{origin_world}"):
            raise TemplateValidationError(
                "El mundo activo no existe en el servidor",
                context={"server_id": cmd.server_id, "world": origin_world},
            )
        world_stream = storage.world_snapshot(origin_world)
        try:
            world_bytes = world_stream.read()
        finally:
            world_stream.close()

        now = deps.time.now()
        template_id = deps.ids.new_id()
        archive = build_template_archive(
            name=name,
            version=version,
            origin_world=origin_world,
            properties=properties,
            world_bytes=world_bytes,
        )
        size_bytes = deps.archive.write(template_id, archive)
        template = Template(
            id=template_id,
            name=name,
            version=version,
            size_bytes=size_bytes,
            origin_server_id=cmd.server_id,
            origin_world=origin_world,
            created_at=now,
            updated_at=now,
        )
        await deps.repository.save(template)
        return template_to_view(template)


class ApplyTemplateUseCase:
    """Aplica (reproduce) una plantilla sobre un servidor existente."""

    def __init__(self, deps: TemplateDeps) -> None:
        self._deps = deps

    async def apply(self, cmd: ApplyTemplateCommand) -> ApplyTemplateResult:
        deps = self._deps
        if not cmd.server_id:
            raise TemplateValidationError(
                "server_id requerido",
                context={"server_id": cmd.server_id},
            )
        template = await deps.repository.get(cmd.template_id)
        if template is None:
            raise TemplateNotFoundError(
                "La plantilla no existe",
                context={"template_id": cmd.template_id},
            )
        parsed = open_template_archive(deps.archive.read(cmd.template_id))
        target = _clean_name(cmd.world_name or parsed.world_name)
        storage = deps.storage.for_server(cmd.server_id)
        if storage.exists(f"worlds/{target}"):
            raise TemplateWorldExistsError(
                "El mundo de destino ya existe en el servidor",
                context={"server_id": cmd.server_id, "world": target},
            )

        await self._restore_world(storage, target, parsed.world_bytes)
        properties = dict(parsed.properties)
        properties["level-name"] = target
        await deps.config.update_properties(
            cmd.server_id,
            properties,
            actor_id=cmd.actor_id,
        )
        return ApplyTemplateResult(
            template=template_to_view(template),
            world_name=target,
        )

    async def _restore_world(
        self,
        storage: ServerStoragePort,
        target: str,
        world_bytes: bytes,
    ) -> None:
        stream = io.BytesIO(world_bytes)
        try:
            storage.write_snapshot(f"worlds/{target}", stream)
        finally:
            stream.close()
        if not storage.exists(f"worlds/{target}/{_LEVEL_DAT}"):
            storage.remove(f"worlds/{target}")
            raise TemplateCorruptError(
                "La plantilla no aporta un Mundo válido (sin level.dat)",
                context={"world": target},
            )


class ListTemplatesUseCase:
    """Lista las plantillas (metadata) del panel."""

    def __init__(self, deps: TemplateDeps) -> None:
        self._deps = deps

    async def list_templates(self) -> list[TemplateView]:
        templates = await self._deps.repository.list()
        return [template_to_view(template) for template in templates]


class GetTemplateUseCase:
    """Devuelve una plantilla por id."""

    def __init__(self, deps: TemplateDeps) -> None:
        self._deps = deps

    async def get(self, template_id: str) -> TemplateView | None:
        template = await self._deps.repository.get(template_id)
        if template is None:
            return None
        return template_to_view(template)


class DeleteTemplateUseCase:
    """Elimina una plantilla: metadata + artefacto."""

    def __init__(self, deps: TemplateDeps) -> None:
        self._deps = deps

    async def delete(self, cmd: DeleteTemplateCommand) -> None:
        deps = self._deps
        template = await deps.repository.get(cmd.template_id)
        if template is None:
            raise TemplateNotFoundError(
                "La plantilla no existe",
                context={"template_id": cmd.template_id},
            )
        await deps.repository.delete(cmd.template_id)
        deps.archive.remove(cmd.template_id)


# -- helpers -----------------------------------------------------------------


def _profile_config(
    deps: TemplateDeps,
    profile: ConfigProfile | None,
) -> tuple[str, dict[str, str]]:
    if profile is None:
        version = str(deps.settings.get("server.default_version", "LATEST"))
        return version, {}
    return profile.version, dict(profile.properties)


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or cleaned in (".", "..") or cleaned.startswith("."):
        raise TemplateValidationError(
            "Nombre de plantilla/mundo inválido",
            context={"name": name},
        )
    if any(separator in cleaned for separator in ("/", "\\")):
        raise TemplateValidationError(
            "El nombre no puede contener separadores de ruta",
            context={"name": name},
        )
    if len(cleaned) > 255:
        raise TemplateValidationError(
            "El nombre supera 255 caracteres",
            context={"name": name},
        )
    return cleaned
