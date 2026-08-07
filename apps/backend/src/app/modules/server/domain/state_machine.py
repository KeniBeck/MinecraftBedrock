"""Máquina de estados del dominio Server (Blueprint §16.3, hallazgo M1).

Estado del servidor = máquina de estados explícita con transiciones validadas.
Los estados son los del ``ServerState`` del kernel (dominio); el estado interno
del runtime (``RuntimeState``) nunca llega en crudo a los consumidores.
"""

from __future__ import annotations

from app.kernel.ports.runtime import ServerState
from app.modules.server.domain.errors import ServerStateError

_ALLOWED_TRANSITIONS: dict[ServerState, frozenset[ServerState]] = {
    ServerState.CREATED: frozenset({ServerState.STARTING, ServerState.REMOVED}),
    ServerState.STARTING: frozenset(
        {ServerState.RUNNING, ServerState.STOPPING, ServerState.CRASHED, ServerState.REMOVED}
    ),
    ServerState.RUNNING: frozenset(
        {ServerState.STOPPING, ServerState.CRASHED, ServerState.REMOVED}
    ),
    ServerState.STOPPING: frozenset(
        {ServerState.STOPPED, ServerState.CRASHED, ServerState.REMOVED}
    ),
    ServerState.STOPPED: frozenset({ServerState.STARTING, ServerState.REMOVED}),
    ServerState.CRASHED: frozenset({ServerState.STARTING, ServerState.REMOVED}),
    ServerState.REMOVED: frozenset(),
}


def allowed_transitions(state: ServerState) -> frozenset[ServerState]:
    """Destinos válidos desde ``state``."""
    return _ALLOWED_TRANSITIONS[state]


def can_transition(current: ServerState, target: ServerState) -> bool:
    """¿Es válida la transición ``current`` → ``target``?"""
    return target in _ALLOWED_TRANSITIONS[current]


def assert_can_transition(current: ServerState, target: ServerState) -> None:
    """Lanza ``ServerStateError`` si la transición no está permitida."""
    if not can_transition(current, target):
        raise ServerStateError(
            f"Transición de estado inválida: {current} → {target}",
            context={"current": current, "target": target},
        )
