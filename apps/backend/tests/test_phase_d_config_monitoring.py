from __future__ import annotations

import asyncio
import struct
from pathlib import Path
from unittest.mock import patch

from app.modules.configuration.infrastructure.reader import BedrockConfigurationReader
from app.modules.monitoring.infrastructure.raknet_probe import (
    _RAKNET_MAGIC,
    RakNetStatusProbe,
    _parse_pong,
)


class DummySettings:
    def get(self, key: str, default: object = None) -> object:
        if key == "server.default_version":
            return "LATEST"
        if key == "storage.base_path":
            return "/tmp/bedrockpanel"
        return default


def test_configuration_reader_maps_server_properties_to_environment(tmp_path: Path) -> None:
    props_file = tmp_path / "server.properties"
    props_file.write_text(
        "server-name=My Bedrock\n"
        "max-players=12\n"
        "gamemode=survival\n"
        "difficulty=hard\n"
        "level-name=world\n",
        encoding="utf-8",
    )

    reader = BedrockConfigurationReader(DummySettings(), properties_path=props_file)
    config = asyncio.run(reader.desired_config("server-1"))

    assert config.version == "LATEST"
    assert config.environment["SERVER_NAME"] == "My Bedrock"
    assert config.environment["MAX_PLAYERS"] == "12"
    assert config.environment["GAMEMODE"] == "survival"
    assert config.environment["DIFFICULTY"] == "hard"
    assert config.environment["LEVEL_NAME"] == "world"


def test_configuration_reader_rejects_invalid_values(tmp_path: Path) -> None:
    props_file = tmp_path / "server.properties"
    props_file.write_text("max-players=1000\n", encoding="utf-8")

    reader = BedrockConfigurationReader(DummySettings(), properties_path=props_file)

    try:
        asyncio.run(reader.desired_config("server-1"))
    except ValueError as exc:
        assert "max-players" in str(exc)
    else:
        raise AssertionError("Expected validation error for invalid max-players")


def test_raknet_probe_reports_online_when_udp_reply_is_received() -> None:
    class FakeSocket:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.sent: tuple[bytes, tuple[str, int]] | None = None
            self.timeout: float | None = None

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def sendto(self, payload: bytes, address: tuple[str, int]) -> None:
            self.sent = (payload, address)

        def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
            del size
            return b"\x01\x00", ("127.0.0.1", 19132)

        def close(self) -> None:
            return None

    target = "app.modules.monitoring.infrastructure.raknet_probe.socket.socket"
    with patch(target, return_value=FakeSocket()) as socket_factory:
        probe = RakNetStatusProbe()
        result = probe.probe("127.0.0.1", 19132, timeout=0.1)

    assert result.online is True
    assert result.latency_ms >= 0.0

    payload, address = socket_factory.return_value.sent or (b"", ("", 0))
    assert address == ("127.0.0.1", 19132)
    assert payload[0] == 0x01
    assert len(payload) == 33
    assert payload[9:25] == _RAKNET_MAGIC


def test_raknet_probe_reports_offline_when_timeout_occurs() -> None:
    class TimeoutSocket:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.timeout: float | None = None

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def sendto(self, payload: bytes, address: tuple[str, int]) -> None:
            del payload, address
            return None

        def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
            del size
            raise TimeoutError("boom")

        def close(self) -> None:
            return None

    target = "app.modules.monitoring.infrastructure.raknet_probe.socket.socket"
    with patch(target, return_value=TimeoutSocket()):
        probe = RakNetStatusProbe()
        result = probe.probe("127.0.0.1", 19132, timeout=0.1)

    assert result.online is False


def _bedrock_pong(players: int, max_players: int) -> bytes:
    """Construye un ``ID_UNCONNECTED_PONG`` real de BDS con el conteo dado."""
    motd = (
        "MCPE;Survival Server;766;1.21.50;"
        f"{players};{max_players};13253860892328930865;Bedrock level;Survival;"
        "1;19132;19133"
    )
    data = motd.encode("utf-8")
    return (
        bytes([0x1C])
        + b"\x00" * 8  # ping time
        + b"\x00" * 8  # server GUID
        + struct.pack(">H", len(data))
        + data
    )


def test_raknet_probe_parses_players_from_bedrock_pong() -> None:
    class PongSocket:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def settimeout(self, timeout: float) -> None:
            del timeout
            return None

        def sendto(self, payload: bytes, address: tuple[str, int]) -> None:
            del payload, address
            return None

        def recvfrom(self, size: int) -> tuple[bytes, tuple[str, int]]:
            del size
            return _bedrock_pong(7, 10), ("127.0.0.1", 19132)

        def close(self) -> None:
            return None

    target = "app.modules.monitoring.infrastructure.raknet_probe.socket.socket"
    with patch(target, return_value=PongSocket()):
        probe = RakNetStatusProbe()
        result = probe.probe("127.0.0.1", 19132, timeout=0.1)

    assert result.online is True
    assert result.players_online == 7
    assert result.players_max == 10


def test_parse_pong_ignores_non_bedrock_payloads() -> None:
    # Paquete de longitud insuficiente / id incorrecto → (0, 0) sin excepción.
    assert _parse_pong(b"\x01\x00") == (0, 0)
    assert _parse_pong(b"\x1c" + b"\x00" * 16) == (0, 0)
    # Datos de longitud declarada mayor que la disponible → (0, 0).
    assert _parse_pong(b"\x1c" + b"\x00" * 16 + b"\xff\xffMCPE;x;0;0;a;b") == (0, 0)
