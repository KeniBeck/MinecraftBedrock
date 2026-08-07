"""Routers HTTP + WebSocket del módulo Console (vertical slice §16).

- REST: enviar comando (con prioridad) y consultar buffer.
- WS mínimo por servidor (ADR-002, Accepted): un canal por servidor para logs/
  consola en vivo reusando ``ConsoleOutputRouter``/``ConsoleSubscription``.
  AuthN por token en el handshake y AuthZ por membresía (mismo criterio que
  REST). Solo lo mínimo: sin canales globales, sin ``resume`` por ``seq``
  avanzado ni rate limiting (Fase H). El resume básico por ``after_seq`` que ya
  ofrece ``ConsoleSubscription.stream()`` se acepta como query param.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import APIRouter, Depends, Request, WebSocket

from app.bootstrap.security import (
    get_container,
    require_server_action,
    ws_identity,
)
from app.kernel.events.event import EventEnvelope
from app.kernel.ports.access import Identity
from app.modules.console.api.schemas import (
    BufferResponse,
    CommandAckResponse,
    ConsoleLineResponse,
    SendCommandRequest,
)
from app.modules.console.application.commands import SendCommand
from app.modules.console.application.facade import ConsoleFacade
from app.modules.console.domain.command import CommandPriority
from app.modules.console.domain.console_log import ConsoleLine
from app.modules.console.domain.events import CONSOLE_OUTPUT

router = APIRouter(tags=["console"])

# Códigos de cierre WS (IETF 6455/6454): 4401 authN fallida, 4403 authZ denegada.
_WS_AUTH_FAILED = 4401
_WS_FORBIDDEN = 4403


def _facade(request: Request) -> ConsoleFacade:
    return get_container(request).console_facade


@router.post(
    "/servers/{server_id}/console/commands",
    response_model=CommandAckResponse,
    status_code=202,
    summary="Enviar comando a la consola",
)
async def send_command(
    server_id: str,
    request: Request,
    body: SendCommandRequest,
    identity: Identity = Depends(require_server_action("server.console.write")),
) -> CommandAckResponse:
    ack = await _facade(request).send_command(
        SendCommand(
            server_id=server_id,
            command=body.command,
            priority=CommandPriority(body.priority),
            actor_id=identity.id,
        )
    )
    return CommandAckResponse(
        server_id=ack.server_id,
        command=ack.command,
        priority=ack.priority.value,
        seq=ack.seq,
        at=ack.at,
    )


@router.get(
    "/servers/{server_id}/console/buffer",
    response_model=BufferResponse,
    summary="Buffer de logs de un servidor",
)
async def get_buffer(
    server_id: str,
    request: Request,
    count: int | None = None,
    identity: Identity = Depends(require_server_action("server.console.read")),
) -> BufferResponse:
    del identity
    view = await _facade(request).get_buffer(server_id, count=count)
    return BufferResponse(
        lines=[
            ConsoleLineResponse(seq=line.seq, server_id=line.server_id, line=line.line)
            for line in view.lines
        ],
        high_water_mark=view.high_water_mark,
    )


@router.websocket("/servers/{server_id}/console/ws")
async def console_ws(
    websocket: WebSocket,
    server_id: str,
    after_seq: int | None = None,
) -> None:
    """Canal WS por servidor: consola/logs en vivo (ADR-002 mínimo).

    AuthN en el handshake (token por query/header) y AuthZ por membresía. Se
    hace ``race`` entre el stream de la suscripción y ``websocket.receive()``
    para terminar limpiamente cuando el cliente se desconecta (evita fugas de
    tareas al esperar líneas en vivo que no llegan).
    """
    container = websocket.app.state.container
    await websocket.accept()

    identity = await ws_identity(websocket, container)
    if identity is None:
        await websocket.close(code=_WS_AUTH_FAILED)
        return

    decision = await container.iam_facade.access_control.authorize(
        identity, "server.console.read", server_id
    )
    if not decision.allowed:
        await websocket.close(code=_WS_FORBIDDEN)
        return

    subscription = await container.console_facade.subscribe(server_id, after_seq=after_seq)
    receive_task = asyncio.create_task(websocket.receive())
    iterator = subscription.stream().__aiter__()
    try:
        while True:
            next_task = asyncio.ensure_future(iterator.__anext__())
            done, _ = await asyncio.wait(
                {next_task, receive_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if next_task in done:
                line = next_task.result()
                await websocket.send_json(_envelope(server_id, line))
                continue
            next_task.cancel()
            with suppress(asyncio.CancelledError):
                await next_task
            message = receive_task.result()
            if message["type"] == "websocket.disconnect":
                break
            receive_task = asyncio.create_task(websocket.receive())
    except StopAsyncIteration:
        pass
    finally:
        await subscription.close()
        receive_task.cancel()
        with suppress(asyncio.CancelledError):
            await receive_task


def _envelope(server_id: str, line: ConsoleLine) -> dict[str, object]:
    """Serializa una línea de consola en la envolvente §13.2."""
    envelope = EventEnvelope(
        event=CONSOLE_OUTPUT,
        scope="console",
        payload={"line": line.line},
        seq=line.seq,
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
