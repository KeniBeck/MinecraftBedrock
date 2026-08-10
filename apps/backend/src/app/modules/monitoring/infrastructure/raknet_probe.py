"""Probe de estado para servidores Bedrock usando RakNet UDP.

Envía un **unconnected ping válido** de RakNet (0x01 + timestamp + magic +
GUID); BDS no responde a un ping malformado, así que el probe debe construir el
paquete completo (§21 hallazgo: el `\\x01\\x00` anterior daba siempre
``offline`` y el servidor real jamás pasaba a ``running``).

Además de ``online``/``latency_ms``, parseea el ``ID_UNCONNECTED_PONG`` (0x1c)
que BDS devuelve en la respuesta para extraer el conteo real de jugadores
(``players_online``/``players_max``) del campo de datos del pong — el formato
``MCPE;motd;protocol;version;players;max_players;...`` separado por `;`.
"""

from __future__ import annotations

import socket
import struct
import time

from app.kernel.ports.status import ProbeResult

_RAKNET_MAGIC = b"\x00\xff\xff\x00\xfe\xfe\xfe\xfe\xfd\xfd\xfd\xfd\x12\x34\x56\x78"
_UNCONNECTED_PING_ID = 0x01
_UNCONNECTED_PONG_ID = 0x1C
_CLIENT_GUID = b"\x00" * 8


class RakNetStatusProbe:
    """Implementa un ping RakNet (unconnected) para detectar si el servidor responde."""

    def __init__(self, *, timeout: float = 2.0) -> None:
        self._timeout = timeout

    def probe(self, host: str, port: int, timeout: float = 2.0) -> ProbeResult:
        start = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout or self._timeout)
        try:
            sock.sendto(_unconnected_ping(), (host, port))
            payload, _ = sock.recvfrom(1024)
        except (TimeoutError, OSError):
            return ProbeResult(online=False, latency_ms=(time.perf_counter() - start) * 1000.0)
        finally:
            sock.close()

        players_online, players_max = _parse_pong(payload)
        return ProbeResult(
            online=True,
            latency_ms=(time.perf_counter() - start) * 1000.0,
            players_online=players_online,
            players_max=players_max,
        )


def _unconnected_ping() -> bytes:
    """Construye ``ID_UNCONNECTED_PING`` (0x01) con timestamp, magic y GUID."""
    timestamp = struct.pack(">Q", int(time.time() * 1000))
    return bytes([_UNCONNECTED_PING_ID]) + timestamp + _RAKNET_MAGIC + _CLIENT_GUID


def _parse_pong(payload: bytes) -> tuple[int, int]:
    """Extrae ``(players_online, players_max)`` de un ``ID_UNCONNECTED_PONG``.

    Formato RakNet 0x1c: [1B id][8B ping time][8B server GUID][2B len][data].
    El dato de Bedrock es ``MCPE;motd;protocol;version;players;max;...`` separado
    por `;` (lista de servers del menú de BDS). Si el payload no es un pong
    válido o el formato no parsea, devuelve ``(0, 0)`` sin romper el probe.
    """
    if len(payload) < 20 or payload[0] != _UNCONNECTED_PONG_ID:
        return 0, 0
    data_len = struct.unpack_from(">H", payload, 17)[0]
    data = payload[19 : 19 + data_len]
    try:
        fields = data.decode("utf-8", errors="replace").split(";")
    except Exception:  # noqa: BLE001 — un pong raro no debe romper el probe
        return 0, 0
    if len(fields) < 6:
        return 0, 0

    def _int(index: int) -> int:
        try:
            return int(fields[index])
        except (ValueError, IndexError):
            return 0

    return _int(4), _int(5)
