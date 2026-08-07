"""Tests de la entidad ``Server`` (transiciones y spec)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.kernel.ports.runtime import RuntimeSpec, ServerState
from app.modules.server.domain.errors import ServerStateError
from app.modules.server.domain.server import Server, ServerId

NOW = datetime(2026, 1, 1, tzinfo=UTC)

DIGEST_IMAGE = (
    "itzg/minecraft-bedrock-server"
    "@sha256:fd46bd30e7c729eacfeea81bca4a62e7c5957f387f1e377da4d03c66f9a76f3d"
)


def make_server(state: ServerState = ServerState.CREATED) -> Server:
    return Server(
        id=ServerId("srv-1"),
        name="Survival",
        spec=RuntimeSpec(image=DIGEST_IMAGE, tag="", version="1.20.0"),
        state=state,
        created_at=NOW,
        updated_at=NOW,
    )


def state_of(server: Server) -> str:
    """Valor de estado como ``str`` (evita narrowing de mypy en los asserts)."""
    return server.state.value


def test_arranque_permite_parada_y_crash() -> None:
    server = make_server(ServerState.STARTING)
    server.mark_started()
    assert state_of(server) == "running"
    server.request_stop()
    assert state_of(server) == "stopping"
    server.mark_stopped()
    assert state_of(server) == "stopped"


def test_crash_permite_reiniciar() -> None:
    server = make_server(ServerState.CRASHED)
    server.request_start()
    assert server.state == ServerState.STARTING


def test_transicion_invalida_lanza_error() -> None:
    server = make_server(ServerState.CREATED)
    with pytest.raises(ServerStateError):
        server.mark_stopped()


def test_estado_terminal_no_acepta_transiciones() -> None:
    server = make_server(ServerState.REMOVED)
    with pytest.raises(ServerStateError):
        server.request_start()


def test_version_es_la_del_spec() -> None:
    server = make_server()
    assert server.version == "1.20.0"
    assert server.image_ref == DIGEST_IMAGE


def test_change_version_actualiza_sin_compartir_env() -> None:
    server = make_server()
    original_env = server.spec.environment
    server.change_version("1.21.0")
    assert server.spec.version == "1.21.0"
    assert server.spec.environment is not original_env
    assert server.spec.environment == {}
