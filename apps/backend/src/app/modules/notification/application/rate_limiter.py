"""Rate limiting por conexión (token bucket, Blueprint §3.12).

Un ``TokenBucket`` admite ``rate`` tokens por segundo con un tope ``burst``
(ración). Cada mensaje saliente consume un token; si el cubo está vacío se
considera excedido. Usa ``TimeProviderPort`` para ser determinista en tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.kernel.time import TimeProviderPort


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Cuota de mensajes por conexión (configurable vía Settings)."""

    rate_per_second: float = 100.0
    burst: int = 100


class TokenBucketRateLimiter:
    """Cubo de tokens con relleno continuo (tasa fija, tope de ración)."""

    def __init__(
        self,
        config: RateLimitConfig,
        time: TimeProviderPort,
    ) -> None:
        self._config = config
        self._time = time
        self._tokens = float(config.burst)
        self._last = time.now()

    def allow(self) -> bool:
        """Consume un token y devuelve si se permite el mensaje."""
        now = self._time.now()
        elapsed = (now - self._last).total_seconds()
        self._last = now
        if elapsed > 0:
            self._tokens = min(
                float(self._config.burst),
                self._tokens + elapsed * self._config.rate_per_second,
            )
        if self._tokens < 1.0:
            return False
        self._tokens -= 1.0
        return True
