"""Adaptador de streaming en vivo: runtime → buffer + ``CONSOLE.OUTPUT`` (§5.2).

Consume ``ServerRuntimePort.stream_logs`` (``Iterator[bytes]`` real del
contenedor) y normaliza las líneas (decodifica, quita ``\r``, ignora vacías).
El iterador del runtime es **síncrono y bloqueante** (``docker logs
--follow``); se lee en un **hilo worker** para no bloquear el event loop, y las
líneas vuelven al loop vía ``call_soon_threadsafe`` sobre una cola, donde se
vuelcan al buffer publicando un ``CONSOLE.OUTPUT`` por línea (change-log §20).

La cancelación (parada del servidor) no fuerza al hilo: el generador termina
solo cuando Docker cierra el stream (el contenedor se detiene/elimina) y el
hilo sale por EOF. No interpreta negocio: el parseo lo hacen consumidores
declarativos de ``infrastructure/parsers``.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from typing import Any

from app.kernel.events.bus import EventBusPort
from app.kernel.ports.runtime import ServerRuntimePort
from app.modules.console.domain.errors import ConsoleUnavailableError
from app.modules.console.domain.events import console_output
from app.modules.console.infrastructure.store import ConsoleLogWriter

_EOF: Any = object()


class ConsoleLogStream:
    """Vuelca el stream de logs del runtime al buffer y publica cada línea."""

    def __init__(
        self,
        runtime: ServerRuntimePort,
        store: ConsoleLogWriter,
        bus: EventBusPort,
    ) -> None:
        self._runtime = runtime
        self._store = store
        self._bus = bus

    async def consume(self, server_id: str, runtime_id: str | None) -> None:
        """Consume el stream del runtime sin bloquear el event loop.

        El iterador síncrono se lee en un hilo ``daemon``; las líneas se pasan
        de vuelta al loop con ``call_soon_threadsafe`` y aquí se añaden al
        buffer publicando un ``CONSOLE.OUTPUT`` por línea. Si el runtime no
        tiene artefacto se lanza ``CONSOLE.UNAVAILABLE``. La corrutina termina
        con el EOF del stream (el contenedor se detuvo/eliminó) o al cancelarse.
        """
        if runtime_id is None:
            raise ConsoleUnavailableError(
                f"Sin runtime para consumir la consola de {server_id}",
                context={"server_id": server_id},
            )
        queue: asyncio.Queue[Any] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _read() -> None:
            try:
                iterator = self._runtime.stream_logs(runtime_id)
                for line in self._iter_lines(iterator):
                    loop.call_soon_threadsafe(queue.put_nowait, line)
            except Exception as exc:  # noqa: BLE001 — el loop decide cómo propagar
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            else:
                loop.call_soon_threadsafe(queue.put_nowait, _EOF)

        threading.Thread(
            target=_read,
            name=f"console-stream-{server_id}",
            daemon=True,
        ).start()

        while True:
            item = await queue.get()
            if item is _EOF:
                return
            if isinstance(item, BaseException):
                raise item
            record = await self._store.append(server_id, item)
            await self._bus.publish(console_output(server_id, record.line, record.seq))

    @staticmethod
    def _iter_lines(stream: Iterator[bytes]) -> Iterator[str]:
        """Separa el stream de bytes en líneas, tolerando trozos parciales.

        Acumula los bytes pendientes entre chunks; las líneas se decodifican
        UTF-8 (con ``errors="replace"``), se les quita el ``\r`` final y se
        ignoran las vacías. Un resto sin salto de línea al final se emite igual.
        """
        carry = b""
        for chunk in stream:
            carry += chunk
            while True:
                sep = carry.find(b"\n")
                if sep == -1:
                    break
                raw, carry = carry[:sep], carry[sep + 1 :]
                line = raw.decode("utf-8", errors="replace").rstrip("\r")
                if line.strip():
                    yield line
        if carry:
            line = carry.decode("utf-8", errors="replace").rstrip("\r")
            if line.strip():
                yield line
