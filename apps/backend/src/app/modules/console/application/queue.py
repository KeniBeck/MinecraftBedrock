"""Cola de comandos por servidor (Blueprint §16.9: 'sin escrituras concurrentes').

``CommandQueue`` serializa las escrituras a stdin de cada servidor con un
``asyncio.Lock`` por servidor (mismo criterio de serialización que
``OperationGuard`` en Server) y ordena por prioridad con un ``heapq`` por
servidor. Un ``submit`` espera a que su comando se escriba y publica el acuse
``CONSOLE.COMMAND_SENT``.

El ``await asyncio.sleep(0)`` antes de drenar agrupa las suscripciones del
mismo tick del event loop: así la prioridad reordena el batch (HIGH antes que
NORMAL) cuando varios comandos llegan a la vez, en lugar de degradarse a un
orden de llegada estricto cuando la escritura es rápida.
"""

from __future__ import annotations

import asyncio
import heapq
from collections import defaultdict
from dataclasses import dataclass

from app.kernel.events.bus import EventBusPort
from app.kernel.ports.runtime import ServerRuntimePort
from app.kernel.time import TimeProviderPort
from app.modules.console.application.results import CommandAck
from app.modules.console.domain.command import CommandPriority
from app.modules.console.domain.errors import StdinWriteError
from app.modules.console.domain.events import console_command_sent


@dataclass(slots=True)
class _QueuedCommand:
    order: int
    seq: int
    priority: CommandPriority
    command: str
    actor_id: str | None
    runtime_id: str

    def __lt__(self, other: _QueuedCommand) -> bool:
        return (self.order, self.seq) < (other.order, other.seq)

    def __gt__(self, other: _QueuedCommand) -> bool:
        return (self.order, self.seq) > (other.order, other.seq)


class CommandQueue:
    """Cola con prioridad y escritura serializada por servidor."""

    def __init__(
        self,
        runtime: ServerRuntimePort,
        bus: EventBusPort,
        time: TimeProviderPort,
    ) -> None:
        self._runtime = runtime
        self._bus = bus
        self._time = time
        self._heap: dict[str, list[_QueuedCommand]] = {}
        self._seq: dict[str, int] = defaultdict(int)
        self._locks: dict[str, asyncio.Lock] = {}
        self._acks: dict[tuple[str, int], CommandAck] = {}

    async def submit(
        self,
        server_id: str,
        command: str,
        priority: CommandPriority,
        actor_id: str | None,
        runtime_id: str,
    ) -> CommandAck:
        """Encola el comando y espera a que se escriba en stdin.

        Si varios ``submit`` concurren sobre el mismo servidor, se drenan en
        orden de prioridad (y, a igual prioridad, por orden de llegada) sin
        intercalar escrituras.
        """
        entry_seq = self._seq[server_id]
        self._seq[server_id] += 1
        heapq.heappush(
            self._heap.setdefault(server_id, []),
            _QueuedCommand(
                order=priority.order,
                seq=entry_seq,
                priority=priority,
                command=command,
                actor_id=actor_id,
                runtime_id=runtime_id,
            ),
        )
        lock = self._locks.setdefault(server_id, asyncio.Lock())
        await asyncio.sleep(0)
        async with lock:
            heap = self._heap[server_id]
            while heap:
                queued = heapq.heappop(heap)
                try:
                    self._runtime.send_stdin(queued.runtime_id, queued.command.rstrip("\n") + "\n")
                except Exception as exc:  # noqa: BLE001 — normalize en CONSOLE.STDIN_WRITE
                    raise StdinWriteError(
                        f"No se pudo escribir en el stdin de {server_id}",
                        context={"server_id": server_id, "command": queued.command},
                    ) from exc
                ack = CommandAck(
                    server_id=server_id,
                    command=queued.command,
                    priority=queued.priority,
                    seq=queued.seq,
                    at=self._time.now(),
                )
                self._acks[(server_id, queued.seq)] = ack
                await self._bus.publish(
                    console_command_sent(
                        server_id,
                        queued.command,
                        queued.priority,
                        actor_id=queued.actor_id,
                        seq=queued.seq,
                    )
                )
        return self._acks.pop((server_id, entry_seq))
