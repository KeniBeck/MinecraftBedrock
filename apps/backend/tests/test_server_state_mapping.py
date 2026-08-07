"""Tests del mapeo ``RuntimeState`` → ``ServerState`` (Blueprint §4.1, TDD §6.2)."""

from __future__ import annotations

from app.kernel.ports.runtime import RuntimeState, ServerState
from app.modules.server.domain.state_mapping import derive_server_state, map_runtime_state


def test_mapeo_puro_de_la_tabla() -> None:
    assert map_runtime_state(RuntimeState.CREATED) == ServerState.CREATED
    assert map_runtime_state(RuntimeState.STARTING) == ServerState.STARTING
    assert map_runtime_state(RuntimeState.RUNNING) == ServerState.RUNNING
    assert map_runtime_state(RuntimeState.STOPPING) == ServerState.STOPPING
    assert map_runtime_state(RuntimeState.DYING) == ServerState.STOPPING
    assert map_runtime_state(RuntimeState.STOPPED) == ServerState.STOPPED
    assert map_runtime_state(RuntimeState.ABSENT) == ServerState.REMOVED


def test_salida_ordenada_no_es_crash() -> None:
    assert derive_server_state(RuntimeState.STOPPED, requested_stop=True) == ServerState.STOPPED


def test_salida_inesperada_es_crash() -> None:
    assert derive_server_state(RuntimeState.STOPPED, requested_stop=False) == ServerState.CRASHED


def test_ausencia_inesperada_es_crash() -> None:
    assert derive_server_state(RuntimeState.ABSENT, requested_stop=False) == ServerState.CRASHED


def test_estados_activos_ignoran_el_flag() -> None:
    assert derive_server_state(RuntimeState.RUNNING, requested_stop=False) == ServerState.RUNNING
    assert derive_server_state(RuntimeState.STOPPING, requested_stop=True) == ServerState.STOPPING
