"""Pruebas unitarias de ``DockerRuntimeAdapter`` con mocks (FASE A).

No requieren Docker instalado: todo el SDK se simula con ``unittest.mock``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest
from docker.errors import APIError, ImageNotFound, NotFound, requests

from app.infrastructure.runtime import DockerRuntimeAdapter, DockerRuntimeSettings
from app.kernel.errors import (
    ContainerNotFoundError,
    DockerError,
    DockerTimeoutError,
    ImageNotFoundError,
    PortInUseError,
)
from app.kernel.ports.runtime import RuntimeSpec, RuntimeState

BEDROCK_IMAGE = (
    "itzg/minecraft-bedrock-server"
    "@sha256:fd46bd30e7c729eacfeea81bca4a62e7c5957f387f1e377da4d03c66f9a76f3d"
)

RUNNING_ATTRS: dict[str, Any] = {
    "Id": "container-abc",
    "Created": "2026-01-01T00:00:00.000000000Z",
    "Image": "sha256:image-123",
    "RestartCount": 2,
    "Config": {
        "Image": BEDROCK_IMAGE,
        "Env": ["LEVEL_NAME=world", "MOTD=Hola"],
        "Cmd": ["/bin/sh"],
    },
    "State": {
        "Status": "running",
        "Running": True,
        "StartedAt": "2026-01-02T00:00:00.000000000Z",
        "ExitCode": 0,
        "Health": {"Status": "healthy"},
    },
    "NetworkSettings": {"Ports": {"19132/udp": [{"HostPort": "19132"}]}},
    "HostConfig": {
        "Memory": 1073741824,
        "NanoCpus": 1000000000,
        "RestartPolicy": {"Name": "unless-stopped"},
    },
}

STOPPED_ATTRS: dict[str, Any] = {
    "Id": "container-def",
    "Created": "2026-01-01T00:00:00.000000000Z",
    "Image": "sha256:image-456",
    "RestartCount": 1,
    "Config": {
        "Image": BEDROCK_IMAGE,
        "Env": [],
        "Cmd": ["/bin/sh"],
    },
    "State": {
        "Status": "exited",
        "Running": False,
        "StartedAt": "2026-01-02T00:00:00.000000000Z",
        "ExitCode": 1,
    },
    "NetworkSettings": {"Ports": {}},
    "HostConfig": {"Memory": 1073741824, "NanoCpus": 0, "RestartPolicy": {"Name": "no"}},
}


def make_settings(**overrides: Any) -> DockerRuntimeSettings:
    base: dict[str, Any] = {
        "container_name": "panel-test",
        "image": BEDROCK_IMAGE,
        "world_volume": "panel-worlds",
        "data_volume": "panel-data",
        "ports": {"19132/udp": 19132},
        "memory_limit": "1g",
        "cpu_limit": 1.0,
        "restart_policy": "unless-stopped",
    }
    base.update(overrides)
    return DockerRuntimeSettings(**base)


def make_client(*, container: Mock | None = None, not_found: bool = False) -> Mock:
    client = Mock()
    if not_found:
        client.containers.get.side_effect = NotFound("no such container")
    else:
        client.containers.get.return_value = container
    return client


def make_factory(client: Mock) -> Mock:
    factory = Mock()
    factory.create.return_value = client
    return factory


def make_adapter(client: Mock, **settings_overrides: Any) -> DockerRuntimeAdapter:
    return DockerRuntimeAdapter(
        make_settings(**settings_overrides),
        docker_client_factory=make_factory(client),
    )


class _FakeResponse:
    """Stub de ``requests.Response`` para construir ``APIError`` con status."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.url = "http://docker"
        self.reason = "reason"


def make_api_error(status_code: int, message: str) -> APIError:
    return APIError(message, response=_FakeResponse(status_code))


def test_exists_returns_true_when_present() -> None:
    adapter = make_adapter(make_client(container=Mock()))
    assert adapter.exists() is True


def test_exists_returns_false_when_missing() -> None:
    adapter = make_adapter(make_client(not_found=True))
    assert adapter.exists() is False


def test_exists_raises_on_connection_error() -> None:
    client = Mock()
    client.containers.get.side_effect = requests.exceptions.ConnectionError("daemon down")
    adapter = make_adapter(client)
    with pytest.raises(DockerError) as exc:
        adapter.exists()
    assert exc.value.retryable is True


def test_create_if_missing_creates_when_absent() -> None:
    client = make_client(not_found=True)
    adapter = make_adapter(client)
    adapter.create_if_missing()
    client.containers.create.assert_called_once()
    args = client.containers.create.call_args.args
    kwargs = client.containers.create.call_args.kwargs
    assert args[0] == BEDROCK_IMAGE
    assert kwargs["name"] == "panel-test"
    assert kwargs["ports"] == {"19132/udp": 19132}
    assert kwargs["volumes"] == ["panel-data:/data", "panel-worlds:/data/worlds"]
    assert kwargs["restart_policy"] == {"Name": "unless-stopped"}
    assert kwargs["mem_limit"] == "1g"
    assert kwargs["nano_cpus"] == 1_000_000_000
    assert kwargs["detach"] is True


def test_create_if_missing_noop_when_exists() -> None:
    client = make_client(container=Mock())
    adapter = make_adapter(client)
    adapter.create_if_missing()
    client.containers.create.assert_not_called()


def test_create_if_missing_image_not_found() -> None:
    client = make_client(not_found=True)
    client.containers.create.side_effect = ImageNotFound("no such image")
    adapter = make_adapter(client)
    with pytest.raises(ImageNotFoundError):
        adapter.create_if_missing()


def test_start_starts_container() -> None:
    container = Mock()
    container.attrs = RUNNING_ATTRS
    adapter = make_adapter(make_client(container=container))
    adapter.start()
    container.start.assert_called_once()
    assert adapter.is_running() is True


def test_start_raises_when_container_missing() -> None:
    adapter = make_adapter(make_client(not_found=True))
    with pytest.raises(ContainerNotFoundError):
        adapter.start()


def test_start_raises_on_daemon_error() -> None:
    container = Mock()
    container.start.side_effect = make_api_error(500, "internal error")
    adapter = make_adapter(make_client(container=container))
    with pytest.raises(DockerError) as exc:
        adapter.start()
    assert exc.value.code == "INFRA.DOCKER_ERROR"
    assert exc.value.context.get("status_code") == 500


def test_start_raises_on_permission_denied() -> None:
    container = Mock()
    container.start.side_effect = make_api_error(403, "permission denied")
    adapter = make_adapter(make_client(container=container))
    with pytest.raises(DockerError) as exc:
        adapter.start()
    assert exc.value.context.get("status_code") == 403


def test_start_raises_port_in_use() -> None:
    container = Mock()
    container.start.side_effect = make_api_error(409, "port is already allocated")
    adapter = make_adapter(make_client(container=container))
    with pytest.raises(PortInUseError):
        adapter.start()


def test_stop_stops_with_grace() -> None:
    container = Mock()
    adapter = make_adapter(make_client(container=container))
    adapter.stop(grace=15)
    container.stop.assert_called_once_with(timeout=15)


def test_stop_raises_when_container_missing() -> None:
    adapter = make_adapter(make_client(not_found=True))
    with pytest.raises(ContainerNotFoundError):
        adapter.stop()


def test_stop_raises_on_daemon_error() -> None:
    container = Mock()
    container.stop.side_effect = make_api_error(500, "stop failed")
    adapter = make_adapter(make_client(container=container))
    with pytest.raises(DockerError):
        adapter.stop()


def test_restart_restarts_with_grace() -> None:
    container = Mock()
    adapter = make_adapter(make_client(container=container))
    adapter.restart(grace=10)
    container.restart.assert_called_once_with(timeout=10)


def test_remove_removes_container() -> None:
    container = Mock()
    adapter = make_adapter(make_client(container=container))
    adapter.remove()
    container.remove.assert_called_once_with(force=True)


def test_remove_idempotent_when_absent() -> None:
    client = make_client(not_found=True)
    adapter = make_adapter(client)
    adapter.remove()
    assert client.containers.get.call_count >= 1


def test_remove_delete_data_removes_volumes() -> None:
    container = Mock()
    volume = Mock()
    client = make_client(container=container)
    client.volumes.get.return_value = volume
    adapter = make_adapter(client)
    adapter.remove(delete_data=True)
    volume_names = [call.args[0] for call in client.volumes.get.call_args_list]
    assert volume_names == ["panel-data", "panel-worlds"]
    volume.remove.assert_called_with(force=True)


def test_status_maps_running_container() -> None:
    container = Mock()
    container.attrs = RUNNING_ATTRS
    adapter = make_adapter(make_client(container=container))
    status = adapter.status()
    assert status.running is True
    assert status.healthy is True
    assert status.container_id == "container-abc"
    assert status.container_name == "panel-test"
    assert status.image == BEDROCK_IMAGE
    assert status.image_id == "sha256:image-123"
    assert status.created_at == "2026-01-01T00:00:00.000000000Z"
    assert status.started_at == "2026-01-02T00:00:00.000000000Z"
    assert status.status == RuntimeState.RUNNING
    assert status.health == "healthy"
    assert status.ports == {"19132/udp": 19132}
    assert status.restart_count == 2


def test_status_maps_stopped_container() -> None:
    container = Mock()
    container.attrs = STOPPED_ATTRS
    adapter = make_adapter(make_client(container=container))
    status = adapter.status()
    assert status.running is False
    assert status.healthy is None
    assert status.status == RuntimeState.STOPPED
    assert status.ports == {}
    assert status.restart_count == 1


def test_status_raises_when_container_missing() -> None:
    adapter = make_adapter(make_client(not_found=True))
    with pytest.raises(ContainerNotFoundError):
        adapter.status()


def test_is_running_false_when_absent() -> None:
    adapter = make_adapter(make_client(not_found=True))
    assert adapter.is_running() is False


def test_is_running_false_when_stopped() -> None:
    container = Mock()
    container.attrs = STOPPED_ATTRS
    adapter = make_adapter(make_client(container=container))
    assert adapter.is_running() is False


def test_logs_returns_decoded_text() -> None:
    container = Mock()
    container.logs.return_value = b"Hello world\n"
    adapter = make_adapter(make_client(container=container))
    assert adapter.logs() == "Hello world\n"
    container.logs.assert_called_once_with(tail=200)


def test_stream_logs_returns_iterador_de_bytes() -> None:
    container = Mock()
    container.logs.return_value = iter([b"line1\n", b"line2\n"])
    adapter = make_adapter(make_client(container=container))

    stream = adapter.stream_logs()

    assert list(stream) == [b"line1\n", b"line2\n"]
    container.logs.assert_called_once_with(stream=True, follow=False, tail="all")


def test_inspect_returns_normalized_dto() -> None:
    container = Mock()
    container.attrs = RUNNING_ATTRS
    adapter = make_adapter(make_client(container=container))
    inspected = adapter.inspect()
    assert inspected.environment == {"LEVEL_NAME": "world", "MOTD": "Hola"}
    assert inspected.command == ["/bin/sh"]
    assert inspected.memory_limit_bytes == 1073741824
    assert inspected.cpu_limit_cores == 1.0
    assert inspected.restart_policy == "unless-stopped"
    assert inspected.exit_code == 0


def test_materialize_creates_container_from_spec() -> None:
    client = make_client(not_found=True)
    adapter = make_adapter(client)
    spec = RuntimeSpec(
        image="itzg/minecraft-bedrock-server",
        tag="2026.1.0",
        environment={"MOTD": "hola", "EULA": "TRUE"},
        ports={"19132/udp": 19132},
        volumes=["data:/data"],
        resources={"memory": "2g", "cpus": 2.0},
    )
    runtime_id = adapter.materialize(spec)
    assert runtime_id == "panel-test"
    assert client.containers.create.call_args.args[0] == "itzg/minecraft-bedrock-server:2026.1.0"
    kwargs = client.containers.create.call_args.kwargs
    assert kwargs["environment"] == {"MOTD": "hola", "EULA": "TRUE"}
    assert kwargs["ports"] == {"19132/udp": 19132}
    assert kwargs["mem_limit"] == "2g"
    assert kwargs["nano_cpus"] == 2_000_000_000


def test_materialize_reemplaza_contenedor_existente() -> None:
    """Si el contenedor ya existe, se elimina y se recrea con el spec nuevo."""
    old = Mock()
    old.remove = Mock()
    client = make_client(container=old)
    # Tras el remove, get debe fallar para que exists() en remove vea el contenedor
    # la primera vez; usamos side_effect que primero devuelve old y luego NotFound
    # solo no es suficiente porque exists+remove+create hacen varios get.
    # Simplificamos: get siempre devuelve old (remove lo borra vía old.remove).
    adapter = make_adapter(client)
    spec = RuntimeSpec(
        image="itzg/minecraft-bedrock-server",
        tag="latest",
        environment={"EULA": "TRUE"},
        ports={"19132/udp": 19134},
    )
    runtime_id = adapter.materialize(spec)
    assert runtime_id == "panel-test"
    old.remove.assert_called()
    client.containers.create.assert_called_once()
    assert client.containers.create.call_args.kwargs["environment"] == {"EULA": "TRUE"}
    assert client.containers.create.call_args.kwargs["ports"] == {"19132/udp": 19134}


def test_get_state_maps_stopped() -> None:
    container = Mock()
    container.attrs = STOPPED_ATTRS
    adapter = make_adapter(make_client(container=container))
    assert adapter.get_state() == RuntimeState.STOPPED


def test_get_health_returns_dict() -> None:
    container = Mock()
    container.attrs = RUNNING_ATTRS
    adapter = make_adapter(make_client(container=container))
    health = adapter.get_health()
    assert health["health"] == "healthy"
    assert health["healthy"] is True


def test_get_resources_parses_stats() -> None:
    container = Mock()
    container.stats.return_value = {
        "cpu_stats": {"cpu_usage": {"total_usage": 12345}, "system_cpu_usage": 67890},
        "memory_stats": {"usage": 1024, "limit": 2048},
    }
    adapter = make_adapter(make_client(container=container))
    resources = adapter.get_resources()
    assert resources["memory_usage_bytes"] == 1024
    assert resources["cpu_percent"] is None


def test_get_exit_code_returns_int() -> None:
    container = Mock()
    container.attrs = STOPPED_ATTRS
    adapter = make_adapter(make_client(container=container))
    assert adapter.get_exit_code() == 1


def test_timeout_maps_to_docker_timeout_error() -> None:
    client = Mock()
    client.containers.get.side_effect = requests.exceptions.Timeout("timeout")
    adapter = make_adapter(client)
    with pytest.raises(DockerTimeoutError):
        adapter.status()


def test_runtime_id_mismatch_raises() -> None:
    adapter = make_adapter(make_client(container=Mock()))
    with pytest.raises(ContainerNotFoundError):
        adapter.start(runtime_id="other-container")


def test_client_factory_failure_propagates_translated_error() -> None:
    factory = Mock()
    factory.create.side_effect = DockerError(
        "No se pudo construir el cliente de Docker",
        context={"reason": "client_init_failed"},
        retryable=True,
    )
    adapter = DockerRuntimeAdapter(make_settings(), docker_client_factory=factory)
    with pytest.raises(DockerError) as exc:
        adapter.exists()
    assert exc.value.retryable is True
    assert exc.value.context["reason"] == "client_init_failed"


def test_client_factory_used_lazily_and_cached() -> None:
    client = make_client(not_found=True)
    factory = make_factory(client)
    adapter = DockerRuntimeAdapter(make_settings(), docker_client_factory=factory)
    assert factory.create.call_count == 0
    adapter.exists()
    adapter.exists()
    assert factory.create.call_count == 1


def test_native_permission_error_maps_to_docker_error() -> None:
    container = Mock()
    container.start.side_effect = PermissionError(13, "Permission denied")
    adapter = make_adapter(make_client(container=container))
    with pytest.raises(DockerError) as exc:
        adapter.start()
    assert exc.value.retryable is False
    assert exc.value.context.get("reason") is None or exc.value.context


def test_native_os_error_maps_to_retryable_docker_error() -> None:
    container = Mock()
    container.start.side_effect = OSError(104, "Connection reset by peer")
    adapter = make_adapter(make_client(container=container))
    with pytest.raises(DockerError) as exc:
        adapter.start()
    assert exc.value.retryable is True


def test_status_maps_oom_killed() -> None:
    attrs = dict(RUNNING_ATTRS)
    attrs["State"] = dict(attrs["State"], OOMKilled=True, Running=False, Status="exited")
    container = Mock()
    container.attrs = attrs
    adapter = make_adapter(make_client(container=container))
    status = adapter.status()
    assert status.oom_killed is True
    assert status.running is False
