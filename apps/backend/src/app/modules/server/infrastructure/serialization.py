"""Serialización del agregado ``Server`` ↔ fila (Fase A paso 2).

Separa el mapeo del repositorio para poder testear la redondez sin BBDD:
``RuntimeSpec`` (dataclass del kernel) se guarda como ``jsonb`` y se reconstruye
filtrando por los campos vigentes (robusto ante evolución futura del spec).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.kernel.ports.runtime import RuntimeSpec, ServerState
from app.modules.server.domain.server import Server, ServerId
from app.modules.server.infrastructure.models import ServerRow


def spec_to_dict(spec: RuntimeSpec) -> dict[str, Any]:
    """Serializa el ``RuntimeSpec`` a JSON (vía ``dataclasses.asdict``)."""
    return asdict(spec)


def spec_from_dict(data: dict[str, Any]) -> RuntimeSpec:
    """Reconstruye el ``RuntimeSpec`` ignorando campos desconocidos."""
    fields = {name for name in RuntimeSpec.__dataclass_fields__ if name in data}
    return RuntimeSpec(**{name: data[name] for name in fields})


def server_to_row(server: Server) -> dict[str, Any]:
    """Proyección de la entidad a los campos de ``ServerRow``."""
    return {
        "id": server.id.value,
        "name": server.name,
        "image": server.spec.image,
        "tag": server.spec.tag,
        "version": server.spec.version,
        "spec": spec_to_dict(server.spec),
        "state": server.state.value,
        "runtime_id": server.runtime_id,
        "desired_config_rev": server.desired_config_rev,
        "applied_config_rev": server.applied_config_rev,
        "created_at": server.created_at,
        "updated_at": server.updated_at,
    }


def server_from_row(row: ServerRow) -> Server:
    """Reconstruye la entidad ``Server`` desde una ``ServerRow``."""
    return Server(
        id=ServerId(row.id),
        name=row.name,
        spec=spec_from_dict(dict(row.spec)),
        state=ServerState(row.state),
        runtime_id=row.runtime_id,
        desired_config_rev=row.desired_config_rev,
        applied_config_rev=row.applied_config_rev,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
