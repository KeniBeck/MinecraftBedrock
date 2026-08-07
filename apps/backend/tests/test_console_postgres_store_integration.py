"""Integración de ``PostgresConsoleLogStore`` (Fase A paso 2, opt-in).

Se ejecutan con ``uv run pytest -m integration``; requieren Postgres de test
(``BEDROCK_PANEL_TEST_DATABASE_URL``) y se saltan si no está disponible.
Verifican persistencia, rehidratación con ``seq`` continuo y retención acotada.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.console.infrastructure.postgres_store import PostgresConsoleLogStore

pytestmark = pytest.mark.integration


async def test_append_y_get_roundtrip(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = PostgresConsoleLogStore(db_session_factory, max_lines=1000)

    await store.append("srv-1", "línea a")
    await store.append("srv-1", "línea b")

    log = await store.get("srv-1")
    assert log.high_water_mark == 1
    assert [line.line for line in log.tail()] == ["línea a", "línea b"]


async def test_rehidrata_con_seq_continuo_al_reiniciar(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store_1 = PostgresConsoleLogStore(db_session_factory, max_lines=1000)
    await store_1.append("srv-1", "a")
    await store_1.append("srv-1", "b")

    store_2 = PostgresConsoleLogStore(db_session_factory, max_lines=1000)
    log = await store_2.get("srv-1")

    assert [line.seq for line in log.tail()] == [0, 1]
    assert log.high_water_mark == 1
    record = await store_2.append("srv-1", "c")
    assert record.seq == 2


async def test_retencion_acota_filas_y_mantiene_seq(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = PostgresConsoleLogStore(db_session_factory, max_lines=5, prune_every=5)
    for i in range(12):
        await store.append("srv-1", f"l{i}")

    fresh = PostgresConsoleLogStore(db_session_factory, max_lines=5, prune_every=5)
    log = await fresh.get("srv-1")

    assert [line.line for line in log.tail()] == ["l7", "l8", "l9", "l10", "l11"]
    assert log.high_water_mark == 11
    record = await fresh.append("srv-1", "l12")
    assert record.seq == 12


async def test_buffer_por_servidor_independiente(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = PostgresConsoleLogStore(db_session_factory, max_lines=10)
    await store.append("srv-a", "a0")
    await store.append("srv-b", "b0")
    await store.append("srv-b", "b1")

    fresh = PostgresConsoleLogStore(db_session_factory, max_lines=10)
    log_a = await fresh.get("srv-a")
    log_b = await fresh.get("srv-b")
    assert [line.line for line in log_a.tail()] == ["a0"]
    assert [line.line for line in log_b.tail()] == ["b0", "b1"]
    assert log_b.high_water_mark == 1
