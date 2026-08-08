"""Tests de integración del gateway WebSocket ``/ws`` (Fase H §16.13).

Verifica el handshake (authN), suscripción/desuscripción de canales, resume
por ``seq`` y las respuestas de control. NOTA: como ``TestClient`` corre la app
en un bucle separado, la difusión en vivo (fan-out del bus) se cubre en los
tests unitarios de ``EventDispatcher``/``ConnectionManager``; aquí se valida el
contrato del socket (mismo criterio que los WS mínimos §ADR-002).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.bootstrap.main import create_app
from app.modules.notification.infrastructure.memory import InMemoryEventLogRepository
from tests.test_api_integration import (
    container_of,
    create_server,
    login,
    make_container,
    seed_admin,
    seed_viewer,
)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """App FastAPI con el container de dobles + super_admin sembrado."""
    container = make_container(storage_root=tmp_path / "storage")
    seed_admin(container)
    app = create_app(container=container)
    with TestClient(app) as test_client:
        yield test_client


class TestGatewayAuth:
    def test_ws_sin_token_cierra_4401(self, client: TestClient) -> None:
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect("/api/v1/ws") as ws,
        ):
            ws.receive_json()
        assert exc_info.value.code == 4401

    def test_ws_con_token_invalido_cierra_4401(self, client: TestClient) -> None:
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect("/api/v1/ws?token=basura") as ws,
        ):
            ws.receive_json()
        assert exc_info.value.code == 4401

    def test_ws_valido_responde_a_subscribe_global(self, client: TestClient) -> None:
        auth = login(client, "root")
        token = auth["Authorization"].removeprefix("Bearer ")
        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            ws.send_text('{"action":"subscribe","channels":["global"]}')
            response = ws.receive_json()
        assert response["type"] == "subscribed"
        assert response["results"][0]["channel"] == "global"
        assert response["results"][0]["allowed"] is True


class TestGatewaySubscribe:
    def test_servidor_sin_membresia_rechazado(self, client: TestClient) -> None:
        seed_viewer(container_of(client))
        root = login(client, "root")
        server_id = create_server(client, root)
        auth = login(client, "lurker")
        token = auth["Authorization"].removeprefix("Bearer ")
        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            ws.send_json({"action": "subscribe", "channels": [f"server:{server_id}"]})
            response = ws.receive_json()
        assert response["type"] == "subscribed"
        assert response["results"][0]["allowed"] is False

    def test_root_super_admin_puede_suscribirse_a_servidor(self, client: TestClient) -> None:
        auth = login(client, "root")
        token = auth["Authorization"].removeprefix("Bearer ")
        server_id = create_server(client, auth)
        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            ws.send_json({"action": "subscribe", "channels": [f"server:{server_id}"]})
            response = ws.receive_json()
        assert response["results"][0]["allowed"] is True

    def test_mensaje_json_invalido_cierra(self, client: TestClient) -> None:
        auth = login(client, "root")
        token = auth["Authorization"].removeprefix("Bearer ")
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(f"/api/v1/ws?token={token}") as ws,
        ):
            ws.send_text("no-json")
            ws.receive_json()
        assert exc_info.value.code == 4408


class TestGatewayResume:
    def test_resume_devuelve_eventos_persistidos(self, client: TestClient) -> None:
        auth = login(client, "root")
        token = auth["Authorization"].removeprefix("Bearer ")
        log = event_log_of(client)
        log.clear()
        log.seed("SERVER.CREATED", "server", server_id="s1")  # seq 1
        log.seed("SERVER.STARTED", "server", server_id="s1")  # seq 2

        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            ws.send_json({"action": "resume", "last_seq": 0, "channels": ["server:s1"]})
            response = ws.receive_json()
        assert response["type"] == "resume"
        assert [e["event"] for e in response["events"]] == ["SERVER.CREATED", "SERVER.STARTED"]
        assert response["exceeded"] is False

    def test_resume_con_last_seq_filtra(self, client: TestClient) -> None:
        auth = login(client, "root")
        token = auth["Authorization"].removeprefix("Bearer ")
        log = event_log_of(client)
        log.clear()
        log.seed("SERVER.CREATED", "server", server_id="s1")  # seq 1
        log.seed("SERVER.STARTED", "server", server_id="s1")  # seq 2

        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            ws.send_json({"action": "resume", "last_seq": 1, "channels": ["server:s1"]})
            response = ws.receive_json()
        assert [e["event"] for e in response["events"]] == ["SERVER.STARTED"]


def event_log_of(client: TestClient) -> InMemoryEventLogRepository:
    facade: Any = container_of(client).notification_facade
    repo = facade.event_log
    assert isinstance(repo, InMemoryEventLogRepository)
    return repo
