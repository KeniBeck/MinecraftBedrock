"""Probe de estado para servidores Bedrock usando RakNet UDP.

Envía un **unconnected ping válido** de RakNet (0x01 + timestamp + magic +
GUID); BDS no responde a un ping malformado, así que el probe debe construir el
paquete completo (§21 hallazgo: el `\\x01\\x00` anterior daba siempre
``offline`` y el servidor real jamás pasaba a ``running``).
"""

from __future__ import annotations

import socket
import struct
import time

from app.kernel.ports.status import ProbeResult

_RAKNET_MAGIC = b"\x00\xff\xff\x00\xfe\xfe\xfe\xfe\xfd\xfd\xfd\xfd\x12\x34\x56\x78"
_UNCONNECTED_PING_ID = 0x01
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
            sock.recvfrom(1024)
        except (TimeoutError, OSError):
            return ProbeResult(online=False, latency_ms=(time.perf_counter() - start) * 1000.0)
        finally:
            sock.close()

        return ProbeResult(online=True, latency_ms=(time.perf_counter() - start) * 1000.0)


def _unconnected_ping() -> bytes:
    """Construye ``ID_UNCONNECTED_PING`` (0x01) con timestamp, magic y GUID."""
    timestamp = struct.pack(">Q", int(time.time() * 1000))
    return bytes([_UNCONNECTED_PING_ID]) + timestamp + _RAKNET_MAGIC + _CLIENT_GUID
