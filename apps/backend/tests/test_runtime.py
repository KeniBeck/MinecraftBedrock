"""Pruebas unitarias de ``DockerRuntimeAdapter`` multi-servidor con mocks.

No requieren Docker installado: el SDK se simula con un doble que modela **N
contenedores** (``{runtime_id: contenedor}``), generalizando el fake de FASE A
(que modelaba un único contenedor global). Verifican que dos ``server_id``
distintos coexisten y que parar/borrar uno no toca al otro.
"""

from __future__ import annotations

from collections.abc import Callable
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


def _spec(server_id: str = "srv-1", **overrides: Any) -> RuntimeSpec:
    data: dict[str, Any] = {
        "image": "itzg/minecraft-bedrock-server",
        "tag": "latest",
        "environment": {"EULA": "TRUE"},
        "ports": {"19132/udp": 19132},
        "volumes": [f"/data/{server_id}:/data"],
        "labels": {"bedrockpanel.server_id": server_id},
    }
    data.update(overrides)
    return RuntimeSpec(
        image=data["image"],
        tag=data["tag"],
        environment=data["environment"],
        ports=data["ports"],
        volumes=data["volumes"],
        labels=data["labels"],
        resources=data.get("resources", {}),
    )


class FakeContainer:
    """Doble de un contenedor Docker dentro del dict del cliente fake."""

    def __init__(
        self,
        name: str,
        attrs: dict[str, Any] | None = None,
        on_remove: Callable[[], None] | None = None,
    ) -> None:
        self.name = name
        self.attrs = dict(attrs or RUNNING_ATTRS)
        self.start = Mock()
        self.stop = Mock()
        self.restart = Mock()
        self.remove = Mock(side_effect=lambda **kwargs: on_remove() if on_remove else None)
        self.kill = Mock()
        self.logs = Mock()
        self.stats = Mock(return_value={})
        self.attach_socket = Mock()


class FakeContainers:
    """``client.containers`` con un dict ``{runtime_id: FakeContainer}``."""

    def __init__(self) -> None:
        self._rev: dict[str, FakeContainer] = {}
        self.created: list[tuple[str, str, dict[str, Any]]] = []

    def list_all(self) -> list[FakeContainer]:
        return list(self._rev.values())

    def get(self, runtime_id: str) -> FakeContainer:
        container = self._rev.get(runtime_id)
        if container is None:
            raise NotFound(f"no such container: {runtime_id}")
        return container

    def create(self, image_ref: str, **kwargs: Any) -> FakeContainer:
        name: str = kwargs["name"]

        def _on_remove() -> None:
            self._rev.pop(name, None)

        container = FakeContainer(name, on_remove=_on_remove)
        self._rev[name] = container
        self.created.append((image_ref, name, kwargs))
        return container


class FakeClient:
    """Cliente Docker con contenedores indexados por ``runtime_id``."""

    def __init__(self) -> None:
        self.containers = FakeContainers()
        self.volumes = Mock()


def make_factory(client: FakeClient) -> Mock:
    factory = Mock()
    factory.create.return_value = client
    return factory


def make_settings(**overrides: Any) -> DockerRuntimeSettings:
    base: dict[str, Any] = {"container_prefix": "panel"}
    base.update(overrides)
    return DockerRuntimeSettings(**base)


def make_adapter(
    client: FakeClient | None = None, **settings_overrides: Any
) -> DockerRuntimeAdapter:
    if client is None:
        client = FakeClient()
    return DockerRuntimeAdapter(
        make_settings(**settings_overrides),
        docker_client_factory=make_factory(client),
    )


def seed_container(client: FakeClient, runtime_id: str, *, running: bool = True) -> FakeContainer:
    containers = client.containers

    def _on_remove() -> None:
        containers._rev.pop(runtime_id, None)

    container = FakeContainer(
        runtime_id,
        RUNNING_ATTRS if running else STOPPED_ATTRS,
        on_remove=_on_remove,
    )
    containers._rev[runtime_id] = container
    return container


class _FakeResponse:
    """Stub de ``requests.Response`` para construir ``APIError`` con status."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.url = "http://docker"
        self.reason = "reason"


def make_api_error(status_code: int, message: str) -> APIError:
    return APIError(message, response=_FakeResponse(status_code))


# -- exists ---------------------------------------------------------------


def test_exists_returns_true_when_present() -> None:
    client = FakeClient()
    seed_container(client, "panel-srv-1")
    adapter = make_adapter(client)
    assert adapter.exists("panel-srv-1") is True


def test_exists_returns_false_when_missing() -> None:
    adapter = make_adapter(FakeClient())
    assert adapter.exists("panel-srv-1") is False


def test_exists_requires_runtime_id() -> None:
    adapter = make_adapter(FakeClient())
    with pytest.raises(DockerError):
        adapter.exists()


# start ------------------------------------------------------------------


def test_start_starts_container() -> None:
    client = FakeClient()
    container = seed_container(client, "panel-srv-1")
    adapter = make_adapter(client)
    adapter.start("panel-srv-1")
    container.start.assert_called_once()
    assert adapter.is_running("panel-srv-1") is True


def test_start_requires_runtime_id() -> None:
    adapter = make_adapter(FakeClient())
    with pytest.raises(DockerError):
        adapter.start()


def test_start_raises_when_container_missing() -> None:
    adapter = make_adapter(FakeClient())
    with pytest.raises(ContainerNotFoundError):
        adapter.start("panel-srv-1")


def test_start_raises_port_in_use() -> None:
    client = FakeClient()
    container = seed_container(client, "panel-srv-1")
    container.start.side_effect = make_api_error(409, "port is already allocated")
    adapter = make_adapter(client)
    with pytest.raises(PortInUseError):
        adapter.start("panel-srv-1")


def test_stop_stops_with_grace() -> None:
    client = FakeClient()
    container = seed_container(client, "panel-srv-1", running=True)
    adapter = make_adapter(client)
    adapter.stop("panel-srv-1", grace=15)
    container.stop.assert_called_once_with(timeout=15)


def test_restart_restarts_with_grace() -> None:
    client = FakeClient()
    container = seed_container(client, "panel-srv-1")
    adapter = make_adapter(client)
    adapter.restart("panel-srv-1", grace=10)
    container.restart.assert_called_once_with(timeout=10)


def test_remove_removes_container() -> None:
    client = FakeClient()
    seed_container(client, "panel-srv-1")
    adapter = make_adapter(client)
    adapter.remove("panel-srv-1")
    assert not adapter.exists("panel-srv-1")


def test_remove_idempotent_when_absent() -> None:
    adapter = make_adapter(FakeClient())
    adapter.remove("panel-srv-1")


def test_inspect_returns_normalized_dto() -> None:
    client = FakeClient()
    seed_container(client, "panel-srv-1")
    adapter = make_adapter(client)
    inspected = adapter.inspect("panel-srv-1")
    assert inspected.environment == {"LEVEL_NAME": "world", "MOTD": "Hola"}
    assert inspected.memory_limit_bytes == 1073741824
    assert inspected.restart_policy == "unless-stopped"
    assert inspected.exit_code == 0


def test_wait_for_stopped_returns_when_absent() -> None:
    adapter = make_adapter(FakeClient())
    adapter.wait_for("panel-srv-1", condition="stopped", timeout=1)


# materialize ---------------------------------------------------------------


def test_materialize_creates_container_named_por_server() -> None:
    client = FakeClient()
    adapter = make_adapter(client)
    runtime_id = adapter.materialize(_spec("srv-1"))
    assert runtime_id == "panel-srv-1"
    assert client.containers.get("panel-srv-1").name == "panel-srv-1"


def test_materialize_two_servers_coexist() -> None:
    client = FakeClient()
    adapter = make_adapter(client)
    id_a = adapter.materialize(_spec("srv-1"))
    id_b = adapter.materialize(_spec("srv-2"))
    assert id_a == "panel-srv-1"
    assert id_b == "panel-srv-2"
    names = sorted(c.name for c in client.containers.list_all())
    assert names == ["panel-srv-1", "panel-srv-2"]


def test_stop_one_does_not_touch_the_other() -> None:
    client = FakeClient()
    c_a = seed_container(client, "panel-srv-1", running=True)
    c_b = seed_container(client, "panel-srv-2", running=True)
    adapter = make_adapter(client)
    adapter.stop("panel-srv-1")
    assert c_a.stop.called
    assert not c_b.stop.called
    assert adapter.is_running("panel-srv-2") is True


def test_remove_one_does_not_touch_the_other() -> None:
    client = FakeClient()
    seed_container(client, "panel-srv-1")
    seed_container(client, "panel-srv-2")
    adapter = make_adapter(client)
    adapter.remove("panel-srv-1")
    assert not adapter.exists("panel-srv-1")
    assert adapter.exists("panel-srv-2") is True


def test_materialize_same_server_replaces_its_own() -> None:
    client = FakeClient()
    adapter = make_adapter(client)
    first = adapter.materialize(_spec("srv-1", ports={"19132/udp": 19132}))
    first_container = client.containers.get(first)
    second = adapter.materialize(_spec("srv-1", ports={"19132/udp": 19300}))
    assert first == second == "panel-srv-1"
    first_container.remove.assert_called()
    names = [c.name for c in client.containers.list_all()]
    assert names.count("panel-srv-1") == 1


def test_materialize_requires_server_id_label() -> None:
    client = FakeClient()
    adapter = make_adapter(client)
    with pytest.raises(DockerError):
        adapter.materialize(RuntimeSpec(image="img", tag="latest", labels={}))


def test_materialize_uses_env_ports_volumes_from_spec() -> None:
    client = FakeClient()
    adapter = make_adapter(client)
    adapter.materialize(
        _spec(
            "srv-1",
            environment={"MOTD": "hola"},
            ports={"19132/udp": 19132},
            resources={"memory": "2g", "cpus": 2.0},
        )
    )
    created = client.containers.created[0]
    kwargs = created[2]
    assert kwargs["environment"] == {"MOTD": "hola"}
    assert kwargs["ports"] == {"19132/udp": 19132}
    assert kwargs["mem_limit"] == "2g"
    assert kwargs["nano_cpus"] == 2_000_000_000


# estado ---------------------------------------------------------------


def test_status_maps_running_container() -> None:
    client = FakeClient()
    seed_container(client, "panel-srv-1", running=True)
    adapter = make_adapter(client)
    status = adapter.status("panel-srv-1")
    assert status.running is True
    assert status.healthy is True
    assert status.container_id == "container-abc"
    assert status.container_name == "panel-srv-1"
    assert status.status == RuntimeState.RUNNING


def test_status_raises_when_container_missing() -> None:
    adapter = make_adapter(FakeClient())
    with pytest.raises(ContainerNotFoundError):
        adapter.status("panel-srv-1")


def test_is_running_false_when_absent() -> None:
    adapter = make_adapter(FakeClient())
    assert adapter.is_running("panel-srv-1") is False


def test_get_state_maps_stopped() -> None:
    client = FakeClient()
    seed_container(client, "panel-srv-1", running=False)
    adapter = make_adapter(client)
    assert adapter.get_state("panel-srv-1") == RuntimeState.STOPPED


def test_get_health_returns_dict() -> None:
    client = FakeClient()
    seed_container(client, "panel-srv-1", running=True)
    adapter = make_adapter(client)
    health = adapter.get_health("panel-srv-1")
    assert health["healthy"] is True


def test_get_resources_parses_stats() -> None:
    client = FakeClient()
    container = seed_container(client, "panel-srv-1")
    container.stats.return_value = {
        "cpu_stats": {"cpu_usage": {"total_usage": 12345}, "system_cpu_usage": 67890},
        "memory_stats": {"usage": 1024, "limit": 2048},
    }
    adapter = make_adapter(client)
    resources = adapter.get_resources("panel-srv-1")
    assert resources["memory_usage_bytes"] == 1024


def test_get_exit_code_returns_int() -> None:
    client = FakeClient()
    seed_container(client, "panel-srv-1", running=False)
    adapter = make_adapter(client)
    assert adapter.get_exit_code("panel-srv-1") == 1


# logs / stream ------------------------------------------------------------


def test_logs_returns_decoded_text() -> None:
    client = FakeClient()
    container = seed_container(client, "panel-srv-1")
    container.logs.return_value = b"Hello world\n"
    adapter = make_adapter(client)
    assert adapter.logs("panel-srv-1") == "Hello world\n"
    container.logs.assert_called_once_with(tail=200)


def test_stream_logs_returns_iterador_de_bytes() -> None:
    client = FakeClient()
    container = seed_container(client, "panel-srv-1")
    container.logs.return_value = iter([b"line1\n", b"line2\n"])
    adapter = make_adapter(client)
    stream = adapter.stream_logs("panel-srv-1")
    assert list(stream) == [b"line1\n", b"line2\n"]
    container.logs.assert_called_once_with(stream=True, follow=True, tail=0)


# errores / traduccion HTTP ----------------------------------------------


def test_timeout_maps_to_docker_timeout_error() -> None:
    client = FakeClient()
    seed_container(client, "panel-srv-1")

    def boom(runtime_id: str) -> FakeContainer:
        raise requests.exceptions.Timeout("timeout")

    client.containers.get = boom  # type: ignore[method-assign]
    adapter = make_adapter(client)
    with pytest.raises(DockerTimeoutError):
        adapter.status("panel-srv-1")


def test_client_factory_failure_propagates_translated_error() -> None:
    factory = Mock()
    factory.create.side_effect = DockerError(
        "No se pudo construir el cliente de Docker",
        context={"reason": "client_init_failed"},
        retryable=True,
    )
    adapter = DockerRuntimeAdapter(make_settings(), docker_client_factory=factory)
    with pytest.raises(DockerError) as exc:
        adapter.exists("panel-srv-1")
    assert exc.value.retryable is True


def test_client_factory_used_lazily_and_cached() -> None:
    client = FakeClient()
    factory = make_factory(client)
    adapter = DockerRuntimeAdapter(make_settings(), docker_client_factory=factory)
    assert factory.create.call_count == 0
    adapter.exists("panel-srv-1")
    adapter.exists("panel-srv-1")
    assert factory.create.call_count == 1


def test_materialize_image_not_found() -> None:
    client = FakeClient()

    def boom(image_ref: str, **kwargs: Any) -> FakeContainer:
        del image_ref, kwargs
        raise ImageNotFound("no such image")

    client.containers.create = boom  # type: ignore[method-assign]
    adapter = make_adapter(client)
    with pytest.raises(ImageNotFoundError):
        adapter.materialize(_spec("srv-1"))


def test_native_permission_error_maps_to_docker_error() -> None:
    client = FakeClient()
    container = seed_container(client, "panel-srv-1")
    container.start.side_effect = PermissionError(13, "Permission denied")
    adapter = make_adapter(client)
    with pytest.raises(DockerError) as exc:
        adapter.start("panel-srv-1")
    assert exc.value.retryable is False


def test_native_os_error_maps_to_retryable_docker_error() -> None:
    client = FakeClient()
    container = seed_container(client, "panel-srv-1")
    container.start.side_effect = OSError(104, "Connection reset by peer")
    adapter = make_adapter(client)
    with pytest.raises(DockerError) as exc:
        adapter.start("panel-srv-1")
    assert exc.value.retryable is True


def test_status_maps_oom_killed() -> None:
    client = FakeClient()
    attrs = dict(RUNNING_ATTRS)
    attrs["State"] = dict(attrs["State"], OOMKilled=True, Running=False, Status="exited")
    seed_container(client, "panel-srv-1")
    client.containers._rev["panel-srv-1"].attrs = attrs
    adapter = make_adapter(client)
    status = adapter.status("panel-srv-1")
    assert status.oom_killed is True
    assert status.running is False
