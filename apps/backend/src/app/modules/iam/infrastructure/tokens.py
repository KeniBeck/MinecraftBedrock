"""Servicio de tokens: JWT de acceso (corto) + refresh opaco rotativo (§14.1).

- Access: JWT HS256 con ``sub``/``username``/``roles``/``iat``/``exp``/``iss``.
- Refresh: opaco (``secrets.token_urlsafe``), nunca se persiste en claro; la
  sesión guarda su SHA-256 (tabla ``iam_sessions``).
- Config vía ``SettingsPort``: ``iam.jwt_secret``, ``iam.jwt_issuer``,
  ``iam.access_token_ttl_seconds`` (default 900), ``iam.refresh_token_ttl_seconds``
  (default 2 592 000).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.kernel.ports.access import Identity
from app.kernel.ports.settings import SettingsPort
from app.modules.iam.application.ports import TokenService
from app.modules.iam.domain.errors import TokenExpiredError, TokenInvalidError

_DEV_SECRET = "dev-insecure-secret-change-me"


class JwtTokenService(TokenService):
    """Emite y valida tokens de acceso JWT y refresh opacos."""

    def __init__(self, settings: SettingsPort) -> None:
        self._settings = settings
        self._algorithm = "HS256"

    @property
    def _secret(self) -> str:
        return str(self._settings.get("iam.jwt_secret", _DEV_SECRET))

    @property
    def _issuer(self) -> str:
        return str(self._settings.get("iam.jwt_issuer", "bedrockpanel"))

    @property
    def _access_ttl(self) -> int:
        return int(self._settings.get("iam.access_token_ttl_seconds", 900))

    @property
    def _temp_ttl(self) -> int:
        return int(self._settings.get("iam.temp_token_ttl_seconds", 300))

    def create_access_token(self, identity: Identity) -> str:
        now = datetime.now(UTC)
        claims: dict[str, Any] = {
            "sub": identity.id,
            "username": identity.username,
            "roles": list(identity.roles),
            "iat": now,
            "exp": now + timedelta(seconds=self._access_ttl),
            "iss": self._issuer,
        }
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                issuer=self._issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError("Access token vencido") from exc
        except jwt.InvalidTokenError as exc:
            raise TokenInvalidError("Access token inválido") from exc

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(48)

    def hash_token(self, raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def create_temp_token(self, user_id: str) -> str:
        now = datetime.now(UTC)
        claims: dict[str, Any] = {
            "sub": user_id,
            "purpose": "2fa",
            "iat": now,
            "exp": now + timedelta(seconds=self._temp_ttl),
            "iss": self._issuer,
        }
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)

    def decode_temp_token(self, token: str) -> str:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                issuer=self._issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError("Temp token 2FA vencido") from exc
        except jwt.InvalidTokenError as exc:
            raise TokenInvalidError("Temp token 2FA inválido") from exc
        if claims.get("purpose") != "2fa":
            raise TokenInvalidError("Temp token sin propósito 2FA")
        return str(claims["sub"])
