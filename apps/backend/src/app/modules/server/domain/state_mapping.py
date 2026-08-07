"""Mapeo explícito ``RuntimeState`` → ``ServerState`` (Blueprint §4.1, hallazgo M1).

El dominio Server **jamás ve** ``RuntimeState`` en crudo. Este módulo es el
único punto donde se traduce el estado del runtime (infraestructura) al estado
de dominio, y se testea por separado.

La derivación de ``crashed`` es contextual: una salida del proceso (``stopped``
o ``absent``) que **no** fue precedida de una parada ordenada se considera
crash (TDD §6.2 / evento de runtime ``die``).
"""

from __future__ import annotations

from app.kernel.ports.runtime import RuntimeState, ServerState

_PURE_MAP: dict[RuntimeState, ServerState] = {
    RuntimeState.CREATED: ServerState.CREATED,
    RuntimeState.STARTING: ServerState.STARTING,
    RuntimeState.RUNNING: ServerState.RUNNING,
    RuntimeState.STOPPING: ServerState.STOPPING,
    RuntimeState.DYING: ServerState.STOPPING,
    RuntimeState.STOPPED: ServerState.STOPPED,
    RuntimeState.ABSENT: ServerState.REMOVED,
}


def map_runtime_state(state: RuntimeState) -> ServerState:
    """Traducción pura de la tabla del Blueprint §4.1 (nota M1)."""
    return _PURE_MAP[state]


def derive_server_state(state: RuntimeState, *, requested_stop: bool) -> ServerState:
    """Estado de dominio a partir del runtime, con detección de crash.

    Args:
        state: Estado reportado por el runtime.
        requested_stop: ``True`` si la salida fue precedida de una parada
            ordenada solicitada por el panel.
    """
    if not requested_stop and state in (RuntimeState.STOPPED, RuntimeState.ABSENT):
        return ServerState.CRASHED
    return map_runtime_state(state)
