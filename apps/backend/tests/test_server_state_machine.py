"""Tests de la máquina de estados del dominio Server (Blueprint §16.3)."""

from __future__ import annotations

import pytest

from app.kernel.ports.runtime import ServerState
from app.modules.server.domain.errors import ServerStateError
from app.modules.server.domain.state_machine import (
    allowed_transitions,
    assert_can_transition,
    can_transition,
)


def test_created_permite_starting_y_removed() -> None:
    transitions = allowed_transitions(ServerState.CREATED)
    assert transitions == frozenset({ServerState.STARTING, ServerState.REMOVED})


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ServerState.CREATED, ServerState.STARTING),
        (ServerState.CREATED, ServerState.REMOVED),
        (ServerState.STOPPED, ServerState.STARTING),
        (ServerState.CRASHED, ServerState.STARTING),
        (ServerState.STARTING, ServerState.RUNNING),
        (ServerState.STARTING, ServerState.STOPPING),
        (ServerState.STARTING, ServerState.CRASHED),
        (ServerState.RUNNING, ServerState.STOPPING),
        (ServerState.RUNNING, ServerState.CRASHED),
        (ServerState.STOPPING, ServerState.STOPPED),
        (ServerState.STOPPING, ServerState.CRASHED),
    ],
)
def test_transiciones_validas(current: ServerState, target: ServerState) -> None:
    assert can_transition(current, target)
    assert_can_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ServerState.CREATED, ServerState.RUNNING),
        (ServerState.CREATED, ServerState.STOPPED),
        (ServerState.RUNNING, ServerState.RUNNING),
        (ServerState.STARTING, ServerState.STARTING),
        (ServerState.STOPPED, ServerState.STOPPED),
        (ServerState.REMOVED, ServerState.STARTING),
        (ServerState.REMOVED, ServerState.REMOVED),
        (ServerState.STOPPED, ServerState.RUNNING),
    ],
)
def test_transiciones_invalidas(current: ServerState, target: ServerState) -> None:
    assert not can_transition(current, target)
    with pytest.raises(ServerStateError):
        assert_can_transition(current, target)


def test_removed_es_estado_terminal() -> None:
    assert allowed_transitions(ServerState.REMOVED) == frozenset()
