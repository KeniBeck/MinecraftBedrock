"""Buffer de logs en memoria del módulo Console (Blueprint §16.9).

``ConsoleLog`` es el agregado mínimo: retiene las líneas con un límite (anillo)
y asigna un ``seq`` monótono a cada una. El ``seq`` permite streaming
idempotente: un suscriptor reanuda desde ``since(after_seq)`` sin duplicados ni
huecos (mientras el buffer no descarte líneas por el límite).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ConsoleLine:
    """Value object: una línea de salida con su secuencia por servidor."""

    seq: int
    server_id: str
    line: str


@dataclass(slots=True)
class ConsoleLog:
    """Buffer anillo de líneas con límite y secuencia monótona."""

    server_id: str
    max_lines: int = 1000
    _lines: deque[ConsoleLine] = field(default_factory=deque, repr=False)
    _next_seq: int = 0

    @property
    def high_water_mark(self) -> int:
        """Última secuencia asignada; ``-1`` si el buffer está vacío."""
        return self._next_seq - 1

    @property
    def size(self) -> int:
        return len(self._lines)

    def append(self, line: str) -> ConsoleLine:
        """Añade una línea y devuelve el registro con su ``seq``.

        Si se supera ``max_lines`` se descarta la más antigua (anillo).
        """
        record = ConsoleLine(seq=self._next_seq, server_id=self.server_id, line=line)
        self._next_seq += 1
        self._lines.append(record)
        if len(self._lines) > self.max_lines:
            self._lines.popleft()
        return record

    def tail(self, count: int | None = None) -> list[ConsoleLine]:
        """Últimas ``count`` líneas (todas si ``count`` es ``None``)."""
        if count is not None and count <= 0:
            return []
        lines = list(self._lines)
        if count is not None:
            lines = lines[-count:]
        return lines

    def since(self, after_seq: int) -> list[ConsoleLine]:
        """Líneas con ``seq > after_seq`` en orden ascendente."""
        return [record for record in self._lines if record.seq > after_seq]

    @classmethod
    def from_records(
        cls,
        server_id: str,
        records: Sequence[ConsoleLine],
        *,
        max_lines: int = 1000,
    ) -> ConsoleLog:
        """Reconstruye el buffer desde registros persistidos (rehidratación).

        Preserva los ``seq`` originales y retoma la numeración en
        ``max(seq) + 1``, de modo que el streaming idempotente (cursor
        ``after_seq``) no se reinicia tras un reinicio del proceso. Se aplica el
        mismo límite anillo a los registros recibidos.
        """
        log = cls(server_id=server_id, max_lines=max_lines)
        ordered = sorted(records, key=lambda record: record.seq)
        log._lines = deque(ordered[-max_lines:])
        log._next_seq = ordered[-1].seq + 1 if ordered else 0
        return log
