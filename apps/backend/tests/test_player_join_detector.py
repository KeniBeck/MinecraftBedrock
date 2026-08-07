"""Tests del parser declarativo ``PlayerJoinDetector`` (Console, §7.3).

Verifica que el parser publica ``PLAYER.JOINED``/``PLAYER.LEFT`` con nombre +
XUID y que el módulo Player **no** publica estos eventos (los publica Console).
"""

from __future__ import annotations

from app.infrastructure.events.bus import InProcessEventBus
from app.infrastructure.parsers.player_join_detector import PlayerJoinDetector
from app.kernel.events.event import DomainEvent
from app.modules.console.domain.events import CONSOLE_OUTPUT_TOPIC, console_output
from app.modules.player.domain.events import (
    PLAYER_JOINED,
    PLAYER_JOINED_TOPIC,
    PLAYER_LEFT,
    PLAYER_LEFT_TOPIC,
)


def make_detector(bus: InProcessEventBus) -> tuple[list[DomainEvent], list[DomainEvent]]:
    joined: list[DomainEvent] = []
    left: list[DomainEvent] = []
    bus.subscribe(PLAYER_JOINED_TOPIC, joined.append)
    bus.subscribe(PLAYER_LEFT_TOPIC, left.append)
    bus.subscribe(CONSOLE_OUTPUT_TOPIC, PlayerJoinDetector(bus=bus))
    return joined, left


async def test_join_detector_publica_player_joined() -> None:
    bus = InProcessEventBus()
    joined, left = make_detector(bus)

    await bus.publish(console_output("srv-1", "Player connected: Steve, xuid: 2535467050498296", 7))

    assert left == []
    assert len(joined) == 1
    assert joined[0].type == PLAYER_JOINED
    assert joined[0].server_id == "srv-1"
    assert joined[0].payload == {
        "server_id": "srv-1",
        "name": "Steve",
        "xuid": "2535467050498296",
    }


async def test_left_detector_publica_player_left() -> None:
    bus = InProcessEventBus()
    joined, left = make_detector(bus)

    await bus.publish(
        console_output("srv-1", "Player disconnected: Alex, xuid: 2535467050498297", 8)
    )

    assert joined == []
    assert len(left) == 1
    assert left[0].type == PLAYER_LEFT
    assert left[0].server_id == "srv-1"
    assert left[0].payload["name"] == "Alex"
    assert left[0].payload["xuid"] == "2535467050498297"


async def test_left_detector_captura_xuid_con_sufijo_pfid() -> None:
    bus = InProcessEventBus()
    joined, left = make_detector(bus)

    await bus.publish(
        console_output(
            "srv-1",
            "Player disconnected: CrafterTec, xuid: 2535473172645342, pfid: AB09BB81504BE8B1",
            8,
        )
    )

    assert joined == []
    assert len(left) == 1
    assert left[0].type == PLAYER_LEFT
    assert left[0].payload["name"] == "CrafterTec"
    assert left[0].payload["xuid"] == "2535473172645342"


async def test_timed_out_tambien_es_player_left() -> None:
    bus = InProcessEventBus()
    joined, left = make_detector(bus)

    await bus.publish(console_output("srv-1", "Player timed out: Alex, xuid: 2535467050498297", 9))

    assert joined == []
    assert len(left) == 1
    assert left[0].type == PLAYER_LEFT


async def test_detector_ignora_lineas_no_relacionadas() -> None:
    bus = InProcessEventBus()
    joined, left = make_detector(bus)

    await bus.publish(console_output("srv-1", "Save complete.", 10))
    await bus.publish(console_output("srv-1", "Level name: Bedrock level", 11))

    assert joined == []
    assert left == []


async def test_detector_ignora_lineas_sin_xuid() -> None:
    bus = InProcessEventBus()
    joined, left = make_detector(bus)

    await bus.publish(console_output("srv-1", "Player connected: Steve", 12))

    assert joined == []
    assert left == []


async def test_detector_requiere_server_id() -> None:
    bus = InProcessEventBus()
    joined, left = make_detector(bus)

    await bus.publish(console_output("", "Player connected: Steve, xuid: 2535467050498296", 13))

    assert joined == []
    assert left == []


async def test_detector_es_insensible_a_mayusculas() -> None:
    bus = InProcessEventBus()
    joined, left = make_detector(bus)

    await bus.publish(
        console_output("srv-1", "PLAYER CONNECTED: Steve, XUID: 2535467050498296", 14)
    )

    assert len(joined) == 1
    assert left == []
