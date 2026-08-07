"""Routers del módulo Monitoring (vertical slice, TDD §13.3).

WS mínimo por servidor (ADR-002): ``/servers/{server_id}/monitoring/ws`` emite
snapshots de estado/métricas cada ``poll_interval`` (5 s) con authN por token
en el handshake y authZ por membresía. Cada tick ejecuta el poller (sondeo +
reconciliación de estado) y envía el envelope ``SERVER.STATE`` con
``scope="monitoring"``: es un evento de transporte, no se publica en el bus.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket

from app.bootstrap.security import ws_identity
from app.kernel.events.event import EventEnvelope
from app.modules.monitoring.api.schemas import status_payload
from app.modules.monitoring.application.polling import StatusSnapshot

router = APIRouter(tags=["monitoring"])

_WS_AUTH_FAILED = 4401
_WS_FORBIDDEN = 4403

_SERVER_STATE = "SERVER.STATE"
_SCOPE = "monitoring"


@router.websocket("/servers/{server_id}/monitoring/ws")
async def monitoring_ws(websocket: WebSocket, server_id: str) -> None:
    container = websocket.app.state.container
    await websocket.accept()

    identity = await ws_identity(websocket, container)
    if identity is None:
        await websocket.close(code=_WS_AUTH_FAILED)
        return

    decision = await container.iam_facade.access_control.authorize(
        identity, "server.status.read", server_id
    )
    if not decision.allowed:
        await websocket.close(code=_WS_FORBIDDEN)
        return

    facade = container.monitoring_facade
    interval = facade.poll_interval
    seq = 0
    receive_task = asyncio.create_task(websocket.receive())
    try:
        while True:
            snapshot = await facade.poll_server(server_id)
            if snapshot is not None:
                seq += 1
                await websocket.send_json(_envelope(server_id, snapshot, seq))

            sleep_task = asyncio.ensure_future(asyncio.sleep(interval))
            done, _ = await asyncio.wait(
                {receive_task, sleep_task}, return_when=asyncio.FIRST_COMPLETED
            )
            sleep_task.cancel()
            with suppress(asyncio.CancelledError):
                await sleep_task
            if receive_task in done:
                message = receive_task.result()
                if message["type"] == "websocket.disconnect":
                    break
                receive_task = asyncio.create_task(websocket.receive())
    finally:
        receive_task.cancel()
        with suppress(asyncio.CancelledError):
            await receive_task


def _envelope(server_id: str, snapshot: StatusSnapshot, seq: int) -> dict[str, object]:
    envelope = EventEnvelope(
        event=_SERVER_STATE,
        scope=_SCOPE,
        payload=status_payload(snapshot),
        seq=seq,
        server_id=server_id,
    )
    return {
        "event": envelope.event,
        "server_id": envelope.server_id,
        "scope": envelope.scope,
        "payload": envelope.payload,
        "ts": envelope.ts.isoformat(),
        "seq": envelope.seq,
    }
