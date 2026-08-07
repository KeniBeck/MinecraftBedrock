"""Tests del contrato ``ConsoleLogWriter`` sobre el store en memoria.

Verifica el path de escritura (stream → buffer) que el módulo Console usa vía
``append``: la línea se persiste en el buffer con ``seq`` monótono y el buffer
se crea si no existe (mismo contrato que ``PostgresConsoleLogStore``).
"""

from __future__ import annotations

from app.modules.console.infrastructure.buffer import InMemoryConsoleLogStore


async def test_append_crea_buffer_y_asigna_seq() -> None:
    store = InMemoryConsoleLogStore(max_lines=1000)

    first = await store.append("srv-1", "línea 1")
    second = await store.append("srv-1", "línea 2")

    assert first.seq == 0
    assert second.seq == 1
    log = await store.get("srv-1")
    assert log.high_water_mark == 1
    assert [line.line for line in log.tail()] == ["línea 1", "línea 2"]


async def test_append_respeta_limite_y_seqs_por_servidor() -> None:
    store = InMemoryConsoleLogStore(max_lines=2)

    for i in range(4):
        await store.append("srv-a", f"a{i}")
    await store.append("srv-b", "b0")

    log_a = await store.get("srv-a")
    log_b = await store.get("srv-b")
    assert log_a.size == 2
    assert [line.line for line in log_a.tail()] == ["a2", "a3"]
    assert log_a.high_water_mark == 3
    assert log_b.high_water_mark == 0
