"""Pruebas unitarias de ``DockerClientFactory`` (hardening FASE A)."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from docker.errors import DockerException

from app.infrastructure.runtime.client_factory import DockerFromEnvClientFactory
from app.kernel.errors import DockerError


def test_create_delegates_to_docker_from_env() -> None:
    client = Mock()
    with patch("app.infrastructure.runtime.client_factory.docker") as docker_module:
        docker_module.from_env.return_value = client
        factory = DockerFromEnvClientFactory(timeout=42, version="auto")
        result = factory.create()
    assert result is client
    docker_module.from_env.assert_called_once_with(timeout=42, version="auto")


def test_create_with_base_url_builds_direct_client() -> None:
    client = Mock()
    with patch("app.infrastructure.runtime.client_factory.docker") as docker_module:
        docker_module.DockerClient.return_value = client
        factory = DockerFromEnvClientFactory(base_url="tcp://10.0.0.5:2375", timeout=30)
        result = factory.create()
    assert result is client
    docker_module.DockerClient.assert_called_once_with(
        base_url="tcp://10.0.0.5:2375",
        timeout=30,
        version=None,
    )
    docker_module.from_env.assert_not_called()


def test_create_maps_docker_exception_to_error() -> None:
    with patch(
        "app.infrastructure.runtime.client_factory.docker.from_env",
        side_effect=DockerException("bad host"),
    ):
        factory = DockerFromEnvClientFactory()
        with pytest.raises(DockerError) as exc:
            factory.create()
    assert exc.value.retryable is True
    assert exc.value.context["reason"] == "client_init_failed"


def test_create_maps_permission_in_cause_chain_as_not_retryable() -> None:
    inner = PermissionError(13, "Permission denied")
    wrapped = requests_connection_error(inner)
    with patch(
        "app.infrastructure.runtime.client_factory.docker.from_env",
        side_effect=DockerException("no daemon", wrapped),
    ):
        factory = DockerFromEnvClientFactory()
        with pytest.raises(DockerError) as exc:
            factory.create()
    assert exc.value.retryable is False
    assert exc.value.context["reason"] == "permission_denied"


def test_create_maps_native_permission_error() -> None:
    with patch(
        "app.infrastructure.runtime.client_factory.docker.from_env",
        side_effect=PermissionError(13, "Permission denied"),
    ):
        factory = DockerFromEnvClientFactory()
        with pytest.raises(DockerError) as exc:
            factory.create()
    assert exc.value.retryable is False
    assert exc.value.context["reason"] == "permission_denied"


def test_create_maps_native_os_error_as_retryable() -> None:
    with patch(
        "app.infrastructure.runtime.client_factory.docker.from_env",
        side_effect=OSError(111, "Connection refused"),
    ):
        factory = DockerFromEnvClientFactory()
        with pytest.raises(DockerError) as exc:
            factory.create()
    assert exc.value.retryable is True
    assert exc.value.context["reason"] == "transport_error"


def requests_connection_error(inner: BaseException) -> BaseException:
    error = OSError(inner)
    error.__cause__ = inner
    return error
