"""Tests del rate limiter por conexión (token bucket, Fase H §16.13)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.kernel.time import TimeProviderPort
from app.modules.notification.application.rate_limiter import (
    RateLimitConfig,
    TokenBucketRateLimiter,
)


class FakeClock:
    """Reloj mutable para controlar el avance del tiempo en tests."""

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 1, 1, tzinfo=UTC)

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)

    def now(self) -> datetime:
        return self._now


class TestTokenBucketRateLimiter:
    def test_burst_inicial_permite_tantos_como_racion(self) -> None:
        clock = FakeClock()
        limiter = TokenBucketRateLimiter(RateLimitConfig(rate_per_second=100.0, burst=3), clock)
        assert [limiter.allow() for _ in range(3)] == [True, True, True]
        assert limiter.allow() is False

    def test_relleno_a_tasa_tras_espera(self) -> None:
        clock = FakeClock()
        limiter = TokenBucketRateLimiter(RateLimitConfig(rate_per_second=1.0, burst=2), clock)
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False  # ración agotada
        clock.advance(1.0)  # 1 token recargado
        assert limiter.allow() is True

    def test_tope_no_supera_el_burst(self) -> None:
        clock = FakeClock()
        limiter = TokenBucketRateLimiter(RateLimitConfig(rate_per_second=1.0, burst=2), clock)
        # espera larga: el cubo no acumula por encima del burst
        clock.advance(50.0)
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False

    def test_con_time_provider_falso(self) -> None:
        time_provider: TimeProviderPort = FakeClock()
        limiter = TokenBucketRateLimiter(RateLimitConfig(burst=1), time_provider)
        assert limiter.allow() is True
        assert limiter.allow() is False
