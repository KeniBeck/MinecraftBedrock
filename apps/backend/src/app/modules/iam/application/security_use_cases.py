"""Use cases de seguridad del módulo IAM (Fase H paso 18).

2FA (TOTP + backup codes) y API keys (material con scopes). Ambos flujos usan
los puertos de aplicación; la autorización de quién puede operar sobre otros
usuarios es de Presentación vía ``AccessControlPort`` (fuera de este paso).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

from app.kernel.ids import IdGeneratorPort
from app.kernel.ports.access import Identity
from app.kernel.ports.settings import SettingsPort
from app.kernel.time import TimeProviderPort
from app.modules.iam.application.commands import (
    ConfirmTwoFactorCommand,
    CreateApiKeyCommand,
    EnableTwoFactorCommand,
    RegenerateBackupCodesCommand,
    RevokeApiKeyCommand,
    RotateApiKeyCommand,
    VerifyTwoFactorLoginCommand,
)
from app.modules.iam.application.ports import (
    ApiKey,
    ApiKeyStorePort,
    SecretCipherPort,
    Session,
    SessionStorePort,
    TokenService,
    TotpServicePort,
)
from app.modules.iam.application.results import (
    ApiKeyCreated,
    ApiKeyView,
    AuthResult,
    TwoFactorEnableResult,
)
from app.modules.iam.domain.errors import (
    AccountSuspendedError,
    TwoFactorInvalidError,
    TwoFactorNotEnabledError,
    UserNotFoundError,
)
from app.modules.iam.domain.repository import IamRepositoryPort
from app.modules.iam.domain.user import User, UserStatus


@dataclass(slots=True)
class SecurityDeps:
    """Dependencias de los use cases de 2FA y API keys."""

    repository: IamRepositoryPort
    sessions: SessionStorePort
    api_keys: ApiKeyStorePort
    tokens: TokenService
    cipher: SecretCipherPort
    totp: TotpServicePort
    ids: IdGeneratorPort
    time: TimeProviderPort
    settings: SettingsPort


def _access_ttl(settings: SettingsPort) -> int:
    return int(settings.get("iam.access_token_ttl_seconds", 900))


def _refresh_ttl(settings: SettingsPort) -> timedelta:
    return timedelta(seconds=int(settings.get("iam.refresh_token_ttl_seconds", 2592000)))


class EnableTwoFactorUseCase:
    """Genera secreto TOTP + backup codes y los persiste cifrados (pendiente de confirmar)."""

    def __init__(self, deps: SecurityDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: EnableTwoFactorCommand) -> TwoFactorEnableResult:
        deps = self._deps
        user = await _require_user(self._deps.repository, cmd.user_id)
        secret = deps.totp.generate_secret()
        backup_codes = deps.totp.generate_backup_codes()
        user.totp_secret = deps.cipher.encrypt(secret)
        user.backup_codes = deps.cipher.encrypt(json.dumps(list(backup_codes)))
        await deps.repository.save(user)
        return TwoFactorEnableResult(
            secret=secret,
            provisioning_uri=deps.totp.provisioning_uri(secret, user.username),
            backup_codes=backup_codes,
        )


class ConfirmTwoFactorUseCase:
    """Verifica el código TOTP y marca el 2FA como habilitado."""

    def __init__(self, deps: SecurityDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: ConfirmTwoFactorCommand) -> None:
        deps = self._deps
        user = await _require_user(self._deps.repository, cmd.user_id)
        if user.totp_secret is None:
            raise TwoFactorNotEnabledError("2FA no iniciado: ejecuta enable primero")
        secret = deps.cipher.decrypt(user.totp_secret)
        if not deps.totp.verify(secret, cmd.code):
            raise TwoFactorInvalidError("Código TOTP inválido")
        user.totp_enabled = True
        await deps.repository.save(user)


class VerifyTwoFactorLoginUseCase:
    """Completa el login: valida el segundo factor y emite tokens de sesión."""

    def __init__(self, deps: SecurityDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: VerifyTwoFactorLoginCommand) -> AuthResult:
        deps = self._deps
        now = deps.time.now()
        user_id = deps.tokens.decode_temp_token(cmd.temp_token)
        user = await _require_user(self._deps.repository, user_id)
        if user.status is not UserStatus.ACTIVE:
            raise AccountSuspendedError(
                f"Cuenta suspendida: {user.username}",
                context={"username": user.username},
            )
        await self._verify_code(user, cmd.code)
        refresh_raw = deps.tokens.generate_refresh_token()
        await deps.sessions.create(
            Session(
                id=deps.ids.new_id(),
                user_id=user.id,
                token_hash=deps.tokens.hash_token(refresh_raw),
                expires_at=now + _refresh_ttl(deps.settings),
                created_at=now,
                ip=cmd.ip,
                ua=cmd.ua,
            )
        )
        await deps.repository.touch_last_login(user.id, now)
        identity = _identity_from(user)
        return AuthResult(
            access_token=deps.tokens.create_access_token(identity),
            refresh_token=refresh_raw,
            expires_in=_access_ttl(deps.settings),
            identity=identity,
        )

    async def _verify_code(self, user: User, code: str) -> None:
        deps = self._deps
        if user.totp_secret is None or not user.totp_enabled:
            raise TwoFactorNotEnabledError("La cuenta no tiene 2FA habilitado")
        if deps.totp.verify(deps.cipher.decrypt(user.totp_secret), code):
            return
        backup_codes = self._decrypt_codes(user)
        if backup_codes and deps.totp.verify_backup_code(code, backup_codes):
            remaining = tuple(c for c in backup_codes if c != code)
            user.backup_codes = (
                deps.cipher.encrypt(json.dumps(list(remaining))) if remaining else None
            )
            await deps.repository.save(user)
            return
        raise TwoFactorInvalidError("Código TOTP o backup code inválido")

    def _decrypt_codes(self, user: User) -> tuple[str, ...]:
        if user.backup_codes is None:
            return ()
        raw = self._deps.cipher.decrypt(user.backup_codes)
        return tuple(str(code) for code in json.loads(raw))


class RegenerateBackupCodesUseCase:
    """Regenera los backup codes (el 2FA ya está verificado: enable+confirm)."""

    def __init__(self, deps: SecurityDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: RegenerateBackupCodesCommand) -> tuple[str, ...]:
        deps = self._deps
        user = await _require_user(self._deps.repository, cmd.user_id)
        if not user.totp_enabled:
            raise TwoFactorNotEnabledError("2FA no habilitado en la cuenta")
        codes = deps.totp.generate_backup_codes()
        user.backup_codes = deps.cipher.encrypt(json.dumps(list(codes)))
        await deps.repository.save(user)
        return codes


class CreateApiKeyUseCase:
    """Crea una API key (material visible una única vez, guarda el hash)."""

    def __init__(self, deps: SecurityDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: CreateApiKeyCommand) -> ApiKeyCreated:
        deps = self._deps
        from app.modules.iam.infrastructure.iam_security import generate_api_key_material

        material, key_hash = generate_api_key_material()
        key = ApiKey(
            id=deps.ids.new_id(),
            user_id=cmd.user_id,
            name=cmd.name,
            key_hash=key_hash,
            scopes=cmd.scopes,
            created_at=deps.time.now(),
        )
        await deps.api_keys.create(key)
        return ApiKeyCreated(
            key=ApiKeyView(
                id=key.id,
                name=key.name,
                scopes=key.scopes,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
                expires_at=key.expires_at,
            ),
            material=material,
        )


class ListApiKeysUseCase:
    """Lista las API keys de un usuario (vista pública, sin material)."""

    def __init__(self, deps: SecurityDeps) -> None:
        self._deps = deps

    async def execute(self, user_id: str) -> list[ApiKeyView]:
        keys = await self._deps.api_keys.list_for_user(user_id)
        return [
            ApiKeyView(
                id=key.id,
                name=key.name,
                scopes=key.scopes,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
                expires_at=key.expires_at,
            )
            for key in keys
        ]


class RevokeApiKeyUseCase:
    """Revoca una API key del usuario."""

    def __init__(self, deps: SecurityDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: RevokeApiKeyCommand) -> None:
        await self._deps.api_keys.revoke(cmd.key_id, cmd.user_id)


class RotateApiKeyUseCase:
    """Rota el material de una API key (nuevo hash; el viejo deja de valer)."""

    def __init__(self, deps: SecurityDeps) -> None:
        self._deps = deps

    async def execute(self, cmd: RotateApiKeyCommand) -> ApiKeyCreated:
        deps = self._deps
        from app.modules.iam.infrastructure.iam_security import generate_api_key_material

        material, key_hash = generate_api_key_material()
        await deps.api_keys.rotate(cmd.key_id, cmd.user_id, key_hash)
        keys = await deps.api_keys.list_for_user(cmd.user_id)
        key = next((k for k in keys if k.id == cmd.key_id), None)
        if key is None:
            raise UserNotFoundError(f"API key no encontrada: {cmd.key_id}")
        return ApiKeyCreated(
            key=ApiKeyView(
                id=key.id,
                name=key.name,
                scopes=key.scopes,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
                expires_at=key.expires_at,
            ),
            material=material,
        )


class ResolveApiKeyUseCase:
    """Resuelve el material de una API key a su hash + usuario (para authN)."""

    def __init__(self, deps: SecurityDeps) -> None:
        self._deps = deps

    async def resolve(self, raw: str) -> ApiKey | None:
        deps = self._deps
        from app.modules.iam.infrastructure.iam_security import hash_api_key

        key = await deps.api_keys.get_by_hash(hash_api_key(raw))
        if key is None:
            return None
        if key.expires_at is not None and key.expires_at <= deps.time.now():
            return None
        await deps.api_keys.touch(key.id, deps.time.now())
        return key


async def _require_user(repository: IamRepositoryPort, user_id: str) -> User:
    user = await repository.get(user_id)
    if user is None:
        raise UserNotFoundError(
            f"Usuario no encontrado: {user_id}",
            context={"user_id": user_id},
        )
    return user


def _identity_from(user: User) -> Identity:
    return Identity(
        id=user.id,
        username=user.username,
        roles=tuple(sorted(role.value for role in user.roles)),
    )
