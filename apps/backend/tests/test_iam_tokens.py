"""Tests del servicio de tokens JWT + refresh opaco (§14.1)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.kernel.ports.access import Identity
from app.modules.iam.domain.errors import TokenExpiredError, TokenInvalidError
from app.modules.iam.infrastructure.tokens import JwtTokenService
from tests.conftest import FakeSettings

SECRET = "test-secret"
ISSUER = "test-issuer"


def make_service() -> JwtTokenService:
    return JwtTokenService(
        FakeSettings(
            {
                "iam.jwt_secret": SECRET,
                "iam.jwt_issuer": ISSUER,
                "iam.access_token_ttl_seconds": 900,
            }
        )
    )


def make_identity() -> Identity:
    return Identity(id="u1", username="alice", roles=("admin", "viewer"))


class TestAccessToken:
    def test_emision_y_decode(self) -> None:
        service = make_service()
        token = service.create_access_token(make_identity())
        claims = service.decode_access_token(token)
        assert claims["sub"] == "u1"
        assert claims["username"] == "alice"
        assert set(claims["roles"]) == {"admin", "viewer"}
        assert claims["iss"] == ISSUER

    def test_token_firmado_con_otro_secret_es_invalido(self) -> None:
        service = make_service()
        forged = jwt.encode({"sub": "u2"}, "otro-secret", algorithm="HS256")
        with pytest.raises(TokenInvalidError):
            service.decode_access_token(forged)

    def test_token_vencido_lanza_expired(self) -> None:
        service = make_service()
        now = datetime.now(UTC)
        expired = jwt.encode(
            {
                "sub": "u1",
                "username": "alice",
                "roles": [],
                "iat": now - timedelta(hours=2),
                "exp": now - timedelta(hours=1),
                "iss": ISSUER,
            },
            SECRET,
            algorithm="HS256",
        )
        with pytest.raises(TokenExpiredError):
            service.decode_access_token(expired)


class TestRefreshToken:
    def test_generacion_opaca_y_determinista_en_hash(self) -> None:
        service = make_service()
        raw = service.generate_refresh_token()
        assert raw and " " not in raw and len(raw) >= 32
        assert service.hash_token(raw) == service.hash_token(raw)
        assert service.hash_token(raw) != raw
