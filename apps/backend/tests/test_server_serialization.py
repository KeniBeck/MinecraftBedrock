"""Tests unitarios del mapeo Server ↔ fila (sin BBDD, Fase A paso 2).

La serialización vive aislada del repositorio para poder testear la redondez:
``RuntimeSpec`` → jsonb → ``RuntimeSpec`` y ``Server`` → ``ServerRow`` → ``Server``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.kernel.ports.runtime import RuntimeSpec, ServerState
from app.modules.server.domain.server import Server, ServerId
from app.modules.server.infrastructure.models import ServerRow
from app.modules.server.infrastructure.serialization import (
    server_from_row,
    server_to_row,
    spec_from_dict,
    spec_to_dict,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_spec() -> RuntimeSpec:
    return RuntimeSpec(
        image="itzg/minecraft-bedrock-server",
        tag="latest",
        version="1.20.0",
        environment={"MOTD": "hola", "DIFFICULTY": "normal"},
        ports={"19132/udp": 19132},
        volumes=["/data:/data"],
        resources={"memory_limit": "2g"},
        network="panel",
        user="root",
        labels={"com.panel.managed": "true"},
        healthcheck=None,
        stdin_open=True,
        tty=True,
    )


def make_server(state: ServerState = ServerState.CREATED) -> Server:
    return Server(
        id=ServerId("srv-1"),
        name="Survival",
        spec=make_spec(),
        state=state,
        runtime_id="r-abc",
        desired_config_rev=3,
        applied_config_rev=2,
        created_at=NOW,
        updated_at=NOW,
    )


def test_spec_roundtrip_con_campos_anidados() -> None:
    spec = make_spec()
    restored = spec_from_dict(spec_to_dict(spec))
    assert restored == spec
    assert restored.environment["MOTD"] == "hola"
    assert restored.healthcheck is None


def test_spec_from_dict_ignora_campos_desconocidos() -> None:
    data = spec_to_dict(make_spec())
    data["campo_futuro"] = "x"
    restored = spec_from_dict(data)
    assert not hasattr(restored, "campo_futuro")
    assert restored.version == "1.20.0"


def test_server_to_row_proyecta_campos_desnormalizados() -> None:
    row = server_to_row(make_server())
    assert row["id"] == "srv-1"
    assert row["state"] == "created"
    assert row["image"] == "itzg/minecraft-bedrock-server"
    assert row["tag"] == "latest"
    assert row["version"] == "1.20.0"
    assert row["runtime_id"] == "r-abc"
    assert row["desired_config_rev"] == 3
    assert row["spec"]["ports"] == {"19132/udp": 19132}


def test_server_roundtrip_via_fila() -> None:
    row = ServerRow(**server_to_row(make_server()))
    server = server_from_row(row)
    assert server.id.value == "srv-1"
    assert server.name == "Survival"
    assert server.state == ServerState.CREATED
    assert server.spec == make_spec()
    assert server.created_at == NOW


def test_server_roundtrip_preserva_estado_y_revisiones() -> None:
    server = make_server(state=ServerState.RUNNING)
    server.applied_config_rev = None
    row = ServerRow(**server_to_row(server))
    restored = server_from_row(row)
    assert restored.state == ServerState.RUNNING
    assert restored.applied_config_rev is None
    assert restored.desired_config_rev == 3
