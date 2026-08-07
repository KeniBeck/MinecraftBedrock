"""Tests de integración de la API HTTP/WS (paso de cierre Fase C/D1).

Cubre el vertical slice ``modules/*/api`` de los tres módulos con un
``Container`` de dobles (mismo criterio que las fases previas): repositorios/
almacenes en memoria, runtime fake, fakes de hasher/tokens/hora/ids. Los tests
usan ``TestClient`` (in-process) y verifican authN/authZ, operaciones sobre
servidor, comando consola y el WS mínimo por servidor (ADR-002).

NOTA sobre el WS: la reproducción se prueba con ``after_seq`` (replay del
buffer) porque el fan-out en vivo es responsabilidad de los tests unitarios de
``ConsoleOutputRouter``/``ConsoleSubscription``; además el ``TestClient`` corre
la app en un bucle separado, lo que impediría publicar eventos desde el test.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.bootstrap.config import get_settings
from app.bootstrap.container import Container
from app.bootstrap.main import create_app
from app.infrastructure.db.session import Database, DatabaseSettings
from app.infrastructure.events.bus import InProcessEventBus
from app.infrastructure.runtime import (
    DockerFromEnvClientFactory,
    DockerRuntimeAdapter,
    DockerRuntimeSettings,
)
from app.kernel.ports.access import Identity
from app.kernel.ports.status import ProbeResult
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.application.queue import CommandQueue
from app.modules.console.application.streaming import ConsoleOutputRouter
from app.modules.console.application.use_cases import ConsoleDeps
from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore
from app.modules.console.infrastructure.stream import ConsoleLogStream
from app.modules.iam.application.commands import AssignRoleCommand, CreateUserCommand
from app.modules.iam.application.facade import IamFacade
from app.modules.iam.application.use_cases import IamDeps
from app.modules.iam.domain.role import BuiltinRole
from app.modules.iam.infrastructure.memory import (
    InMemoryAuditStore,
    InMemoryIamRepository,
    InMemorySessionStore,
)
from app.modules.monitoring.application.facade import MonitoringFacade
from app.modules.monitoring.application.polling import StatusPoller
from app.modules.monitoring.infrastructure.memory import InMemoryMetricSampleStore
from app.modules.server.application.facade import ServerFacade
from app.modules.server.application.spec_factory import RuntimeSpecFactory
from app.modules.server.application.use_cases import ServerDeps
from app.modules.server.infrastructure.repository import InMemoryServerRepository
from tests.conftest import (
    FakeConfigurationReader,
    FakeRuntime,
    FakeSettings,
    FakeTime,
    SequenceIds,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed:{password}"


class FakeTokenService:
    """Token service con decode por diccionario (evita JWT/secret en tests)."""

    def __init__(self) -> None:
        self._n = 0
        self._issued: dict[str, dict[str, object]] = {}

    def create_access_token(self, identity: Identity) -> str:
        token = f"at-{identity.id}-{self._n}"
        self._n += 1
        self._issued[token] = {
            "sub": identity.id,
            "username": identity.username,
            "roles": list(identity.roles),
        }
        return token

    def decode_access_token(self, token: str) -> dict[str, object]:
        claims = self._issued.get(token)
        if claims is None:
            from app.modules.iam.domain.errors import TokenInvalidError

            raise TokenInvalidError("token inválido")
        return claims

    def generate_refresh_token(self) -> str:
        token = f"rt-{self._n}"
        self._n += 1
        return token

    def hash_token(self, raw: str) -> str:
        return f"sha256:{raw}"


class FakeProbe:
    """``StatusProbePort`` con resultado inyectado (online por defecto)."""

    def __init__(self, result: ProbeResult | None = None) -> None:
        self._result = result or ProbeResult(online=True, latency_ms=5.0, players_online=3)
        self.calls: list[tuple[str, int]] = []

    def probe(self, host: str, port: int, timeout: float = 2.0) -> ProbeResult:
        del timeout
        self.calls.append((host, port))
        return self._result


def make_container() -> Container:
    """Container de dobles: todos los ports en memoria + runtime fake."""
    settings_port = FakeSettings()
    bus = InProcessEventBus()
    runtime = FakeRuntime()
    time = FakeTime(NOW)

    server_repository = InMemoryServerRepository()
    configuration = FakeConfigurationReader()
    spec_factory = RuntimeSpecFactory(settings_port)
    server_deps = ServerDeps(
        repository=server_repository,
        runtime=runtime,
        bus=bus,
        ids=SequenceIds("srv-1"),
        time=time,
        settings=settings_port,
        configuration=configuration,
        spec_factory=spec_factory,
    )
    server_facade = ServerFacade(
        repository=server_repository,
        configuration=configuration,
        spec_factory=spec_factory,
        deps=server_deps,
    )
    server_facade.register_handlers()

    console_store = InMemoryConsoleLogStore(max_lines=1000)
    console_deps = ConsoleDeps(
        server=server_facade,
        runtime=runtime,
        bus=bus,
        time=time,
        settings=settings_port,
        ids=SequenceIds("sub-1"),
        store=console_store,
    )
    command_queue = CommandQueue(runtime=runtime, bus=bus, time=time)
    output_router = ConsoleOutputRouter(store=console_store, bus=bus)
    console_facade = ConsoleFacade(deps=console_deps, queue=command_queue, router=output_router)
    console_facade.register_handlers()

    iam_repository = InMemoryIamRepository()
    iam_sessions = InMemorySessionStore()
    iam_audit = InMemoryAuditStore()
    iam_deps = IamDeps(
        repository=iam_repository,
        sessions=iam_sessions,
        audit=iam_audit,
        hasher=FakePasswordHasher(),
        tokens=FakeTokenService(),
        bus=bus,
        ids=SequenceIds("user-1", "user-2", "session-1", "session-2"),
        time=time,
        settings=settings_port,
    )
    iam_facade = IamFacade(iam_deps)
    iam_facade.register_handlers()

    console_stream = ConsoleLogStream(runtime=runtime, store=console_store, bus=bus)
    docker_runtime = DockerRuntimeAdapter(
        DockerRuntimeSettings(),
        docker_client_factory=DockerFromEnvClientFactory(),
    )

    monitoring_store = InMemoryMetricSampleStore()
    status_poller = StatusPoller(
        server=server_facade,
        runtime=runtime,
        probe=FakeProbe(),
        store=monitoring_store,
        time=time,
        settings=settings_port,
    )
    monitoring_facade = MonitoringFacade(status_poller, poll_interval=5.0)

    return Container(
        settings=get_settings(),
        database=Database(
            DatabaseSettings(url="postgresql+psycopg://panel:panel@localhost:5432/panel_test")
        ),
        docker_runtime=docker_runtime,
        event_bus=bus,
        server_facade=server_facade,
        server_repository=server_repository,
        console_facade=console_facade,
        console_stream=console_stream,
        iam_facade=iam_facade,
        monitoring_facade=monitoring_facade,
    )


def seed_admin(container: Container) -> None:
    """Crea un super_admin global en la BBDD en memoria (por la facade)."""

    async def _seed() -> None:
        view = await container.iam_facade.create_user(
            CreateUserCommand(
                username="root", password="s3cret!pw", display_name="Root", actor_id="bootstrap"
            )
        )
        await container.iam_facade.assign_role(
            AssignRoleCommand(user_id=view.id, role=BuiltinRole.SUPER_ADMIN, actor_id="bootstrap")
        )

    asyncio.run(_seed())


def seed_viewer(container: Container) -> None:
    """Crea un viewer global sin membresías."""

    async def _seed() -> None:
        view = await container.iam_facade.create_user(
            CreateUserCommand(
                username="lurker",
                password="s3cret!pw",
                display_name="Lurker",
                actor_id="bootstrap",
            )
        )
        await container.iam_facade.assign_role(
            AssignRoleCommand(user_id=view.id, role=BuiltinRole.VIEWER, actor_id="bootstrap")
        )

    asyncio.run(_seed())


@pytest.fixture
def client() -> Iterator[TestClient]:
    """App FastAPI con el container de dobles + super_admin sembrado."""
    container = make_container()
    seed_admin(container)
    app = create_app(container=container)
    with TestClient(app) as test_client:
        yield test_client


def container_of(client: TestClient) -> Container:
    """Contenedor instalado en la app del cliente (``app.state``)."""
    app = cast(Any, client.app)
    container: Container = app.state.container
    return container


def console_store(client: TestClient) -> InMemoryConsoleLogStore:
    """Store en memoria de la consola (para sembrar el buffer)."""
    return cast(InMemoryConsoleLogStore, container_of(client).console_facade.deps.store)


def login(client: TestClient, username: str, password: str = "s3cret!pw") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def create_server(client: TestClient, auth: dict[str, str], name: str = "Survival") -> str:
    response = client.post("/api/v1/servers", json={"name": name}, headers=auth)
    assert response.status_code == 201, response.text
    server_id: str = response.json()["id"]
    return server_id


class TestAuth:
    def test_login_devuelve_tokens_e_identity(self, client: TestClient) -> None:
        body = client.post(
            "/api/v1/auth/login",
            json={"username": "root", "password": "s3cret!pw"},
        ).json()

        assert body["access_token"]
        assert body["refresh_token"]
        assert body["identity"]["username"] == "root"
        assert "super_admin" in body["identity"]["roles"]

    def test_endpoint_protegido_sin_token_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/servers")

        assert response.status_code == 401
        assert response.json()["detail"]["code"].startswith("AUTH.")

    def test_login_invalido_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "root", "password": "mala-clave"},
        )

        assert response.status_code == 401


class TestServers:
    def test_ciclo_vida_completo_via_http(self, client: TestClient) -> None:
        auth = login(client, "root")
        server_id = create_server(client, auth)

        created = client.get(f"/api/v1/servers/{server_id}", headers=auth).json()
        assert created["connection"]["host"] == "localhost"
        assert created["connection"]["port"] == 19132
        assert created["connection"]["port_v6"] == 19133
        assert created["connection"]["address"] == "localhost:19132"

        started = client.post(f"/api/v1/servers/{server_id}/start", headers=auth)
        assert started.status_code == 200
        assert started.json()["state"] == "starting"
        assert started.json()["connection"]["address"] == "localhost:19132"

        stopped = client.post(f"/api/v1/servers/{server_id}/stop", json={"grace": 10}, headers=auth)
        assert stopped.status_code == 200
        assert stopped.json()["state"] == "stopped"

        detail = client.get(f"/api/v1/servers/{server_id}", headers=auth)
        assert detail.status_code == 200
        assert detail.json()["id"] == server_id

        removed = client.delete(f"/api/v1/servers/{server_id}", headers=auth)
        assert removed.status_code == 204

    def test_viewer_no_puede_crear_servidor(self, client: TestClient) -> None:
        seed_viewer(container_of(client))
        auth = login(client, "lurker")

        response = client.post("/api/v1/servers", json={"name": "Nope"}, headers=auth)

        assert response.status_code == 403

    def test_servidor_inexistente_404(self, client: TestClient) -> None:
        auth = login(client, "root")

        response = client.get("/api/v1/servers/no-existe", headers=auth)

        assert response.status_code == 404


class TestConsoleApi:
    def test_comando_consola_aceptado(self, client: TestClient) -> None:
        auth = login(client, "root")
        server_id = create_server(client, auth)
        client.post(f"/api/v1/servers/{server_id}/start", headers=auth)
        asyncio.run(container_of(client).server_facade.mark_started(server_id))

        response = client.post(
            f"/api/v1/servers/{server_id}/console/commands",
            json={"command": "say hola", "priority": "high"},
            headers=auth,
        )

        assert response.status_code == 202
        assert response.json()["server_id"] == server_id
        assert response.json()["priority"] == "high"

    def test_buffer_devuelve_lineas(self, client: TestClient) -> None:
        auth = login(client, "root")
        server_id = create_server(client, auth)
        store = console_store(client)
        asyncio.run(store.append(server_id, "Server started"))

        response = client.get(f"/api/v1/servers/{server_id}/console/buffer", headers=auth)

        assert response.status_code == 200
        assert response.json()["lines"][0]["line"] == "Server started"

    def test_viewer_no_puede_escribir_comando(self, client: TestClient) -> None:
        seed_viewer(container_of(client))
        server_id = create_server(client, login(client, "root"))
        auth = login(client, "lurker")
        response = client.post(
            f"/api/v1/servers/{server_id}/console/commands",
            json={"command": "stop"},
            headers=auth,
        )

        assert response.status_code == 403


class TestConsoleWs:
    def test_ws_sin_token_cierra_4401(self, client: TestClient) -> None:
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect("/api/v1/servers/srv-1/console/ws") as ws,
        ):
            ws.receive_json()

        assert exc_info.value.code == 4401

    def test_ws_viewer_sin_membresia_cierra_4403(self, client: TestClient) -> None:
        seed_viewer(container_of(client))
        auth = login(client, "lurker")
        token = auth["Authorization"].removeprefix("Bearer ")

        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(f"/api/v1/servers/srv-1/console/ws?token={token}") as ws,
        ):
            ws.receive_json()

        assert exc_info.value.code == 4403

    def test_ws_reproduce_buffer_desde_after_seq(self, client: TestClient) -> None:
        auth = login(client, "root")
        token = auth["Authorization"].removeprefix("Bearer ")
        server_id = create_server(client, auth)
        store = console_store(client)
        asyncio.run(store.append(server_id, "primera"))
        asyncio.run(store.append(server_id, "segunda"))

        messages: list[dict[str, Any]] = []
        with client.websocket_connect(
            f"/api/v1/servers/{server_id}/console/ws?token={token}&after_seq=-1"
        ) as ws:
            first = ws.receive_json()
            second = ws.receive_json()
            messages.extend([first, second])

        assert [m["payload"]["line"] for m in messages] == ["primera", "segunda"]
        assert [m["scope"] for m in messages] == ["console", "console"]
        assert [m["event"] for m in messages] == ["CONSOLE.OUTPUT", "CONSOLE.OUTPUT"]
        assert messages[0]["seq"] < messages[1]["seq"]
        assert all(m["server_id"] == server_id for m in messages)


class TestMonitoringWs:
    def test_ws_sin_token_cierra_4401(self, client: TestClient) -> None:
        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect("/api/v1/servers/srv-1/monitoring/ws") as ws,
        ):
            ws.receive_json()

        assert exc_info.value.code == 4401

    def test_ws_viewer_sin_membresia_cierra_4403(self, client: TestClient) -> None:
        seed_viewer(container_of(client))
        auth = login(client, "lurker")
        token = auth["Authorization"].removeprefix("Bearer ")

        with (
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(f"/api/v1/servers/srv-1/monitoring/ws?token={token}") as ws,
        ):
            ws.receive_json()

        assert exc_info.value.code == 4403

    def test_ws_emite_snapshot_de_estado(self, client: TestClient) -> None:
        auth = login(client, "root")
        token = auth["Authorization"].removeprefix("Bearer ")
        server_id = create_server(client, auth)

        with client.websocket_connect(
            f"/api/v1/servers/{server_id}/monitoring/ws?token={token}"
        ) as ws:
            message = ws.receive_json()

        assert message["event"] == "SERVER.STATE"
        assert message["scope"] == "monitoring"
        assert message["server_id"] == server_id
        assert message["payload"]["status"] == "online"
        assert message["payload"]["players"] == 3
        assert "state" in message["payload"]
        assert message["seq"] == 1
