from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

from app.modules.configuration.infrastructure.reader import BedrockConfigurationReader
from app.modules.monitoring.infrastructure.raknet_probe import RakNetStatusProbe


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
            return b"\x01\x00", ("127.0.0.1", 19132)

        def close(self) -> None:
            return None

    target = "app.modules.monitoring.infrastructure.raknet_probe.socket.socket"
    with patch(target, return_value=FakeSocket()):
        probe = RakNetStatusProbe()
        result = probe.probe("127.0.0.1", 19132, timeout=0.1)

    assert result.online is True
    assert result.latency_ms >= 0.0


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
