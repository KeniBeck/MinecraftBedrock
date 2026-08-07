"""Tests del agregado ``ConsoleLog`` (buffer de logs, Blueprint §16.9)."""

from __future__ import annotations

from app.modules.console.domain.console_log import ConsoleLine, ConsoleLog


def make_log(max_lines: int = 1000) -> ConsoleLog:
    return ConsoleLog(server_id="srv-1", max_lines=max_lines)


def test_append_asigna_seq_secuencial() -> None:
    log = make_log()
    assert log.high_water_mark == -1
    first = log.append("línea 1")
    second = log.append("línea 2")
    assert first.seq == 0
    assert second.seq == 1
    assert log.high_water_mark == 1


def test_append_respeta_el_limite_del_anillo() -> None:
    log = make_log(max_lines=3)
    for i in range(5):
        log.append(f"l{i}")
    assert log.size == 3
    assert [line.line for line in log.tail()] == ["l2", "l3", "l4"]
    assert log.high_water_mark == 4


def test_tail_devuelve_las_ultimas_n() -> None:
    log = make_log()
    for i in range(5):
        log.append(f"l{i}")
    assert [line.line for line in log.tail(2)] == ["l3", "l4"]
    assert len(log.tail()) == 5
    assert log.tail(0) == []
    assert log.tail(-1) == []


def test_since_devuelve_solo_las_posteriores_al_cursor() -> None:
    log = make_log()
    for i in range(4):
        log.append(f"l{i}")
    lines = log.since(1)
    assert [line.line for line in lines] == ["l2", "l3"]
    assert log.since(log.high_water_mark) == []


def test_from_records_preserva_seq_y_continua_numeracion() -> None:
    records = [
        ConsoleLine(seq=500, server_id="srv-1", line="a"),
        ConsoleLine(seq=501, server_id="srv-1", line="b"),
        ConsoleLine(seq=502, server_id="srv-1", line="c"),
    ]
    log = ConsoleLog.from_records("srv-1", records, max_lines=1000)
    assert [line.line for line in log.tail()] == ["a", "b", "c"]
    assert [line.seq for line in log.tail()] == [500, 501, 502]
    assert log.high_water_mark == 502
    assert log.append("d").seq == 503


def test_from_records_ordena_aunque_esten_desordenados() -> None:
    records = [
        ConsoleLine(seq=7, server_id="srv-1", line="b"),
        ConsoleLine(seq=3, server_id="srv-1", line="a"),
    ]
    log = ConsoleLog.from_records("srv-1", records)
    assert [line.seq for line in log.tail()] == [3, 7]
    assert log.high_water_mark == 7


def test_from_records_aplica_el_limite_del_anillo() -> None:
    records = [ConsoleLine(seq=i, server_id="srv-1", line=f"l{i}") for i in range(10)]
    log = ConsoleLog.from_records("srv-1", records, max_lines=3)
    assert log.size == 3
    assert [line.line for line in log.tail()] == ["l7", "l8", "l9"]
    assert log.high_water_mark == 9


def test_from_records_vacio_mantiene_seq_cero() -> None:
    log = ConsoleLog.from_records("srv-1", [])
    assert log.high_water_mark == -1
    assert log.append("a").seq == 0
