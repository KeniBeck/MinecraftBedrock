"""Adaptador de streaming: runtime → buffer + ``CONSOLE.OUTPUT`` (§5.2).

Consume ``ServerRuntimePort.stream_logs`` (``Iterator[bytes]`` real del
contenedor), normaliza las líneas (decodifica, quita ``\r``, ignora vacías) y
las vuelca al buffer publicando un ``CONSOLE.OUTPUT`` por línea. No interpreta
negocio: el parseo lo hacen consumidores declarativos de ``infrastructure/parsers``.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.kernel.events.bus import EventBusPort
from app.kernel.ports.runtime import ServerRuntimePort
from app.modules.console.domain.errors import ConsoleUnavailableError
from app.modules.console.domain.events import console_output
from app.modules.console.infrastructure.store import ConsoleLogWriter


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
        """Consume el stream del runtime hasta que se agote o falle.

        Cada línea se añade al buffer (con su ``seq``) y se publica como
        ``CONSOLE.OUTPUT``. Si el runtime no tiene artefacto se lanza
        ``CONSOLE.UNAVAILABLE``.
        """
        if runtime_id is None:
            raise ConsoleUnavailableError(
                f"Sin runtime para consumir la consola de {server_id}",
                context={"server_id": server_id},
            )
        iterator = self._runtime.stream_logs(runtime_id)
        for line in self._iter_lines(iterator):
            record = await self._store.append(server_id, line)
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
