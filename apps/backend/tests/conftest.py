"""Fakes y fixtures compartidos para los tests del módulo Server (Fase B).

Todos los dobles son implementaciones completas de sus Protocolos para pasar
``mypy --strict`` (pyproject incluye ``tests``).
"""

from __future__ import annotations

import io
import os
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Registra los modelos de cada módulo para ``create_all``/``drop_all`` en la
# fixture de integración (Fase A paso 2; Fase C paso 8 añade IAM; Fase D paso
# 10 añade Configuration; Fase E paso 11 añade Player; Fase E paso 12 añade
# World; Fase F paso 13 añade Backup).
import app.modules.backup.infrastructure.models  # noqa: F401
import app.modules.configuration.infrastructure.models  # noqa: F401
import app.modules.console.infrastructure.models  # noqa: F401
import app.modules.iam.infrastructure.models  # noqa: F401
import app.modules.player.infrastructure.models  # noqa: F401
import app.modules.scheduler.infrastructure.models  # noqa: F401
import app.modules.server.infrastructure.models  # noqa: F401
import app.modules.world.infrastructure.models  # noqa: F401
from app.infrastructure.db.base import Base
from app.infrastructure.events.bus import InProcessEventBus
from app.kernel.ports.runtime import RuntimeSpec, RuntimeState
from app.modules.server.application.ports import DesiredConfig
from app.modules.server.application.results import ServerView


class FakeSettings:
    """``SettingsPort`` con un dict inyectado."""

    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self._values: dict[str, Any] = values or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)


class FakeTime:
    """``TimeProviderPort`` con hora fija."""

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now


class SequenceIds:
    """``IdGeneratorPort`` con secuencia determinista."""

    def __init__(self, *values: str) -> None:
        self._values = list(values)
        self._index = 0

    def new_id(self) -> str:
        value = self._values[self._index % len(self._values)]
        self._index += 1
        return value

    def new_id_bytes(self) -> bytes:
        return b"\x00" * 16


class FakeConfigurationReader:
    """``ConfigurationReader`` con valores mutables inyectados."""

    def __init__(
        self,
        version: str = "1.20.0",
        env: dict[str, str] | None = None,
        config_rev: int = 1,
    ) -> None:
        self.version = version
        self.env: dict[str, str] = dict(env or {})
        self.config_rev = config_rev

    async def desired_config(self, server_id: str) -> DesiredConfig:
        del server_id
        return DesiredConfig(
            version=self.version,
            environment=dict(self.env),
            config_rev=self.config_rev,
        )


class FakeRuntime:
    """``ServerRuntimePort`` en memoria que registra cada llamada."""

    def __init__(self) -> None:
        self.specs: dict[str, RuntimeSpec] = {}
        self.states: dict[str, RuntimeState] = {}
        self.materialized: list[str] = []
        self.started: list[str] = []
        self.stopped: list[tuple[str, int]] = []
        self.removed: list[tuple[str, bool]] = []
        self.stdin_writes: list[tuple[str, str]] = []
        self.log_lines: list[bytes] | None = None
        self._next = 0

    def _new_id(self) -> str:
        value = f"r{self._next}"
        self._next += 1
        return value

    def materialize(self, spec: RuntimeSpec) -> str:
        runtime_id = self._new_id()
        self.specs[runtime_id] = spec
        self.states[runtime_id] = RuntimeState.CREATED
        self.materialized.append(runtime_id)
        return runtime_id

    def start(self, runtime_id: str) -> None:
        self.states[runtime_id] = RuntimeState.STARTING
        self.started.append(runtime_id)

    def stop(self, runtime_id: str, grace: int = 30) -> None:
        self.states[runtime_id] = RuntimeState.STOPPED
        self.stopped.append((runtime_id, grace))

    def restart(self, runtime_id: str, grace: int = 30) -> None:
        self.states[runtime_id] = RuntimeState.STARTING
        self.stopped.append((runtime_id, grace))
        self.started.append(runtime_id)

    def remove(self, runtime_id: str, delete_data: bool = False) -> None:
        self.states[runtime_id] = RuntimeState.ABSENT
        self.removed.append((runtime_id, delete_data))

    def get_state(self, runtime_id: str) -> RuntimeState:
        return self.states[runtime_id]

    def get_health(self, runtime_id: str) -> dict[str, Any]:
        del runtime_id
        return {"status": "ok"}

    def get_resources(self, runtime_id: str) -> dict[str, Any]:
        del runtime_id
        return {}

    def get_exit_code(self, runtime_id: str) -> int | None:
        del runtime_id
        return None

    def stream_logs(self, runtime_id: str) -> Iterator[bytes]:
        del runtime_id
        if self.log_lines is not None:
            return iter(self.log_lines)
        return io.BytesIO()

    def send_stdin(self, runtime_id: str, data: str) -> None:
        self.stdin_writes.append((runtime_id, data))

    def wait_for(self, runtime_id: str, condition: str, timeout: int = 60) -> None:
        del runtime_id, condition, timeout

    def signal(self, runtime_id: str, sig: int) -> None:
        del runtime_id, sig


class FakeServerReader:
    """``ServerConsoleReader`` con un dict de ``ServerView`` inyectado."""

    def __init__(self, views: dict[str, ServerView] | None = None) -> None:
        self._views = views or {}
        self.calls: list[str] = []

    async def get_server(self, server_id: str) -> ServerView | None:
        self.calls.append(server_id)
        return self._views.get(server_id)

    async def list_servers(self) -> list[ServerView]:
        return list(self._views.values())


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def runtime() -> FakeRuntime:
    return FakeRuntime()


@pytest.fixture
def configuration() -> FakeConfigurationReader:
    return FakeConfigurationReader()


@pytest_asyncio.fixture
async def db_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Fábrica de sesiones a un Postgres real (solo tests de integración).

    Usa ``BEDROCK_PANEL_TEST_DATABASE_URL`` (default local ``panel_test``),
    crea las tablas de los módulos al empezar y las destruye al terminar. Si no
    hay BBDD disponible, los tests que la soliciten se saltan (mismo criterio
    opt-in que Docker en FASE A).
    """
    url = os.getenv(
        "BEDROCK_PANEL_TEST_DATABASE_URL",
        "postgresql+psycopg://panel:panel@localhost:5432/panel_test",
    )
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
    except Exception as exc:  # noqa: BLE001 — skip si no hay BBDD
        await engine.dispose()
        pytest.skip(f"Postgres de test no disponible: {exc}")

    try:
        yield async_sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()
