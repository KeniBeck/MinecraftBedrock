"""Router WebSocket único del gateway (Blueprint §3.12, TDD §13).

``GET /ws`` es el canal global de eventos para el frontend. Valida el token en
el handshake (query ``?token=`` o header ``Authorization``, vía ``ws_identity``)
y a partir de ahí gestiona suscripciones, diffúnde envelopes en vivo, reenvía
eventos perdidos (resume) y aplica rate limiting al flujo del cliente. Es el
sustituto del gateway completo definido en el TDD §13 (los WS mínimos por
servidor siguen activos para retrocompatibilidad).
"""

from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.bootstrap.security import ws_identity
from app.modules.notification.domain.events import InvalidSubscriptionError
from app.modules.notification.domain.subscription import Channel

router = APIRouter(tags=["notification"])

_WS_AUTH_FAILED = 4401
_WS_BAD_MESSAGE = 4408


def _facade(websocket: WebSocket) -> Any:
    """Facade instalado en el contenedor (evita import circular con bootstrap)."""
    container = websocket.app.state.container
    return container.notification_facade


@router.websocket("/ws")
async def gateway_ws(websocket: WebSocket) -> None:
    """Canal único elástico de eventos en tiempo real (Blueprint §3.12)."""
    await websocket.accept()

    identity = await ws_identity(websocket, websocket.app.state.container)
    if identity is None:
        await websocket.close(code=_WS_AUTH_FAILED)
        return

    facade = _facade(websocket)
    connection = facade.open_connection(identity)
    sender = asyncio.create_task(_sender(websocket, connection))
    try:
        await _pump(websocket, facade, connection)
    finally:
        sender.cancel()
        with suppress(asyncio.CancelledError):
            await sender
        facade.close_connection(connection)


async def _sender(websocket: WebSocket, connection: Any) -> None:
    """Volca el buffer de salida de la conexión al socket hasta cerrar."""
    while True:
        message = await connection.buffer.get()
        if not message:
            break
        await websocket.send_json(message)


def _parse(data: str) -> dict[str, Any]:
    """Parsea un mensaje JSON del cliente; lanza si no es un dict."""
    parsed = json.loads(data)
    if not isinstance(parsed, dict):
        raise ValueError("mensaje no-objeto")
    return parsed


async def _pump(websocket: WebSocket, facade: Any, connection: Any) -> None:
    """Bucle de recepción de mensajes del cliente."""
    while True:
        try:
            data = await websocket.receive_text()
        except WebSocketDisconnect:
            return
        try:
            message: dict[str, Any] = _parse(data)
        except (ValueError, KeyError):
            await websocket.close(code=_WS_BAD_MESSAGE)
            return
        action = message.get("action")
        if not isinstance(action, str):
            await _enqueue(connection, {"type": "error", "code": "NOTI.UNKNOWN_ACTION"})
            continue
        handler = _ACTIONS.get(action)
        if handler is None:
            await _enqueue(connection, {"type": "error", "code": "NOTI.UNKNOWN_ACTION"})
            continue
        try:
            await handler(websocket, facade, connection, message)
        except InvalidSubscriptionError:
            await _enqueue(connection, {"type": "error", "code": "NOTI.INVALID_SUBSCRIPTION"})


async def _handle_subscribe(
    websocket: WebSocket, facade: Any, connection: Any, message: dict[str, Any]
) -> None:
    del websocket
    results = []
    for name in _as_list(message.get("channels")):
        channel = Channel.parse(name)
        result = await facade.subscribe(connection, connection.identity, channel)
        results.append(
            {"channel": result.channel, "allowed": result.allowed, "reason": result.reason}
        )
    await _enqueue(connection, {"type": "subscribed", "results": results})


async def _handle_unsubscribe(
    websocket: WebSocket, facade: Any, connection: Any, message: dict[str, Any]
) -> None:
    del websocket
    for name in _as_list(message.get("channels")):
        await facade.unsubscribe(connection, Channel.parse(name))
    await _enqueue(connection, {"type": "unsubscribed"})


async def _handle_resume(
    websocket: WebSocket, facade: Any, connection: Any, message: dict[str, Any]
) -> None:
    del websocket
    last_seq = int(message.get("last_seq", 0))
    channels = _as_list(message.get("channels"))
    envelopes, exceeded = await facade.resume(last_seq, channels)
    await _enqueue(connection, {"type": "resume", "events": envelopes, "exceeded": exceeded})
    if exceeded:
        await _enqueue(
            connection,
            {"type": "error", "code": "NOTI.RESUME_TOO_LARGE", "last_seq": last_seq},
        )


async def _handle_pong(
    websocket: WebSocket, facade: Any, connection: Any, message: dict[str, Any]
) -> None:
    del websocket, facade, message
    connection.last_pong = True


_ACTIONS = {
    "subscribe": _handle_subscribe,
    "unsubscribe": _handle_unsubscribe,
    "resume": _handle_resume,
    "pong": _handle_pong,
}


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


async def _enqueue(connection: Any, message: dict[str, Any]) -> None:
    connection.buffer.put_nowait(message)
