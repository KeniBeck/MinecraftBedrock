"""Probe simple de estado para servidores Bedrock usando RakNet UDP."""

from __future__ import annotations

import socket
import time

from app.kernel.ports.status import ProbeResult


class RakNetStatusProbe:
    """Implementa un ping mínimo de RakNet para detectar si el servidor responde."""

    def __init__(self, *, timeout: float = 2.0) -> None:
        self._timeout = timeout

    def probe(self, host: str, port: int, timeout: float = 2.0) -> ProbeResult:
        start = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout or self._timeout)
        try:
            sock.sendto(b"\x01\x00", (host, port))
            sock.recvfrom(1024)
        except (TimeoutError, OSError):
            return ProbeResult(online=False, latency_ms=(time.perf_counter() - start) * 1000.0)
        finally:
            sock.close()

        return ProbeResult(online=True, latency_ms=(time.perf_counter() - start) * 1000.0)
