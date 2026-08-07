"""Pruebas de integración del adaptador Docker (FASE A).

Solo se ejecutan con ``uv run pytest -m integration`` y requieren un daemon
Docker disponible. Usan un contenedor real ``alpine`` como sujeto de prueba.
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
from app.kernel.ports.runtime import RuntimeState

pytestmark = pytest.mark.integration

CONTAINER_NAME = "bedrock-panel-integration-test"
IMAGE = "alpine:3.20"


@pytest.fixture(scope="module")
def adapter() -> DockerRuntimeAdapter:
    try:
        client = docker.from_env()
        client.ping()
        client.images.pull(IMAGE)
    except Exception as exc:
        pytest.skip(f"Docker no disponible o sin acceso a la imagen: {exc}")
    settings = DockerRuntimeSettings(
        container_name=CONTAINER_NAME,
        image=IMAGE,
        world_volume="",
        data_volume="",
        ports={},
        memory_limit=None,
        cpu_limit=None,
        restart_policy="no",
        docker_timeout=60,
    )
    return DockerRuntimeAdapter(
        settings,
        docker_client_factory=DockerFromEnvClientFactory(timeout=60),
    )


@pytest.fixture(autouse=True)
def cleanup(adapter: DockerRuntimeAdapter) -> Iterator[None]:
    if adapter.exists():
        adapter.remove()
    yield
    if adapter.exists():
        adapter.remove()


def test_full_lifecycle(adapter: DockerRuntimeAdapter) -> None:
    adapter.create_if_missing()
    assert adapter.exists() is True

    created_status = adapter.status()
    assert created_status.running is False
    assert created_status.status == RuntimeState.CREATED

    adapter.start()
    assert adapter.is_running() is True
    adapter.wait_for(condition="running", timeout=60)

    running_status = adapter.status()
    assert running_status.running is True
    assert running_status.container_name == CONTAINER_NAME
    assert running_status.image == IMAGE

    logs = adapter.logs()
    assert isinstance(logs, str)

    adapter.stop(grace=10)
    assert adapter.is_running() is False

    adapter.restart(grace=10)
    assert adapter.is_running() is True

    adapter.stop(grace=10)
    adapter.remove()
    assert adapter.exists() is False
