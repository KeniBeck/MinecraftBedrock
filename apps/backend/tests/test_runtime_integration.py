"""Pruebas de integración del adaptador Docker multi-servidor (FASE A).

Solo se ejecutan con ``uv run pytest -m integration`` y requieren un daemon
Docker disponible. Usan contenedores reales ``alpine`` como sujetos de prueba,
uno por ``server_id`` ficticio, y comprueban que dos servers coexisten.
"""

from __future__ import annotations

from collections.abc import Iterator

import docker
import pytest

from app.infrastructure.runtime import (
    DockerFromEnvClientFactory,
    DockerRuntimeAdapter,
    DockerRuntimeSettings,
)
from app.kernel.ports.runtime import RuntimeSpec, RuntimeState

pytestmark = pytest.mark.integration

IMAGE = "alpine:3.20"
PREFIX = "bedrock-panel-integration"


def _spec(server_id: str) -> RuntimeSpec:
    return RuntimeSpec(
        image=IMAGE,
        tag="latest",
        environment={"EULA": "TRUE"},
        labels={"bedrockpanel.server_id": server_id},
        stdin_open=True,
        tty=False,
    )


@pytest.fixture(scope="module")
def client() -> docker.DockerClient:
    client = docker.from_env()
    try:
        client.ping()
        client.images.pull(IMAGE)
    except Exception as exc:
        pytest.skip(f"Docker no disponible o sin acceso a la imagen: {exc}")
    return client


@pytest.fixture(scope="module")
def adapter(client: docker.DockerClient) -> DockerRuntimeAdapter:
    return DockerRuntimeAdapter(
        DockerRuntimeSettings(container_prefix=PREFIX, docker_timeout=60),
        docker_client_factory=DockerFromEnvClientFactory(timeout=60),
    )


@pytest.fixture(autouse=True)
def cleanup(adapter: DockerRuntimeAdapter) -> Iterator[None]:
    for server_id in ("it-1", "it-2"):
        runtime_id = f"{PREFIX}-{server_id}"
        if adapter.exists(runtime_id):
            adapter.remove(runtime_id)
    yield
    for server_id in ("it-1", "it-2"):
        runtime_id = f"{PREFIX}-{server_id}"
        if adapter.exists(runtime_id):
            adapter.remove(runtime_id)


def test_dos_servidores_coexisten(
    client: docker.DockerClient, adapter: DockerRuntimeAdapter
) -> None:
    id_a = adapter.materialize(_spec("it-1"))
    id_b = adapter.materialize(_spec("it-2"))
    assert id_a == f"{PREFIX}-it-1"
    assert id_b == f"{PREFIX}-it-2"

    real_names = {c.name for c in client.containers.list(all=True) if c.name in {id_a, id_b}}
    assert real_names == {id_a, id_b}

    adapter.start(id_a)
    assert adapter.is_running(id_a) is True
    # it-2 no se arrancó; sigue parado (independiente).
    assert adapter.is_running(id_b) is False

    adapter.stop(id_a)
    adapter.remove(id_a)
    assert not adapter.exists(id_a)
    # it-2 existe aunque it-1 se borrara.
    assert adapter.exists(id_b) is True


def test_materialize_mismo_server_reemplaza_el_suyo(
    adapter: DockerRuntimeAdapter,
) -> None:
    runtime_id = f"{PREFIX}-it-1"
    first = adapter.materialize(_spec("it-1"))
    status_created = adapter.status(first)
    assert status_created.status == RuntimeState.CREATED
    assert first == runtime_id

    second = adapter.materialize(_spec("it-1"))
    assert second == runtime_id
    assert adapter.exists(runtime_id) is True
