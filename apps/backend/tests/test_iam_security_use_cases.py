"""Tests de 2FA (TOTP) y API keys del módulo IAM (Fase H paso 18)."""

from __future__ import annotations

import pyotp
import pytest

from app.infrastructure.events.bus import InProcessEventBus
from app.modules.iam.application.commands import (
    ConfirmTwoFactorCommand,
    CreateApiKeyCommand,
    DisableTwoFactorCommand,
    EnableTwoFactorCommand,
    LoginCommand,
    RegenerateBackupCodesCommand,
    RevokeApiKeyCommand,
    RotateApiKeyCommand,
    VerifyTwoFactorLoginCommand,
)
from app.modules.iam.application.security_use_cases import (
    ConfirmTwoFactorUseCase,
    CreateApiKeyUseCase,
    DisableTwoFactorUseCase,
    EnableTwoFactorUseCase,
    GetTwoFactorStatusUseCase,
    ListApiKeysUseCase,
    RegenerateBackupCodesUseCase,
    ResolveApiKeyUseCase,
    RevokeApiKeyUseCase,
    RotateApiKeyUseCase,
    SecurityDeps,
    VerifyTwoFactorLoginUseCase,
)
from app.modules.iam.application.use_cases import IamDeps, LoginUseCase
from app.modules.iam.domain.errors import (
    TokenInvalidError,
    TwoFactorInvalidError,
    TwoFactorNotEnabledError,
    TwoFactorRequiredError,
)
from app.modules.iam.domain.role import BuiltinRole
from app.modules.iam.domain.user import User, UserStatus
from app.modules.iam.infrastructure.iam_security import (
    FernetSecretCipher,
    PyotpTotpService,
    hash_api_key,
)
from app.modules.iam.infrastructure.memory import (
    InMemoryApiKeyStore,
    InMemoryAuditStore,
    InMemoryIamRepository,
    InMemoryPermissionRepository,
    InMemorySessionStore,
)
from tests.conftest import FakeSettings, FakeTime, SequenceIds
from tests.test_iam_use_cases import NOW, FakePasswordHasher, FakeTokenService

_FERNET_KEY = "9Dfa2Y5t4kMX6k4oyar_EgtQ1cFcdPE8V_6I688Tu4k="


def make_user(user_id: str = "u1", username: str = "alice") -> User:
    return User(
        id=user_id,
        username=username,
        password_hash="hashed:pass",
        display_name="Alice",
        status=UserStatus.ACTIVE,
        created_at=NOW,
        roles={BuiltinRole.ADMIN},
    )


class Deps:
    def __init__(self) -> None:
        self.repository = InMemoryIamRepository()
        self.sessions = InMemorySessionStore()
        self.audit = InMemoryAuditStore()
        self.api_keys = InMemoryApiKeyStore()
        self.bus = InProcessEventBus()
        self.ids = SequenceIds("u-1", "k-1", "k-2", "s-1")
        self.time = FakeTime(NOW)
        self.settings = FakeSettings({})
        self.hasher = FakePasswordHasher()
        self.tokens = FakeTokenService()
        self.cipher = FernetSecretCipher(_FERNET_KEY)
        self.totp = PyotpTotpService()
        self.security = SecurityDeps(
            repository=self.repository,
            sessions=self.sessions,
            api_keys=self.api_keys,
            tokens=self.tokens,
            cipher=self.cipher,
            totp=self.totp,
            ids=self.ids,
            time=self.time,
            settings=self.settings,
        )
        self.deps = IamDeps(
            repository=self.repository,
            sessions=self.sessions,
            audit=self.audit,
            hasher=self.hasher,
            tokens=self.tokens,
            bus=self.bus,
            ids=self.ids,
            time=self.time,
            settings=self.settings,
            permissions=InMemoryPermissionRepository(),
            api_keys=self.api_keys,
            cipher=self.cipher,
            totp=self.totp,
        )


class TestEnableTwoFactor:
    async def test_genera_secreto_uri_y_backup_codes(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        result = await EnableTwoFactorUseCase(deps.security).execute(
            EnableTwoFactorCommand(user_id="u1")
        )
        assert len(result.secret) == 32
        assert result.provisioning_uri.startswith("otpauth://totp/")
        assert len(result.backup_codes) == 10
        assert all(len(code) == 8 for code in result.backup_codes)

    async def test_secreto_guardado_cifrado(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        result = await EnableTwoFactorUseCase(deps.security).execute(
            EnableTwoFactorCommand(user_id="u1")
        )
        user = await deps.repository.get("u1")
        assert user is not None and user.totp_secret is not None
        assert user.totp_secret != result.secret
        assert deps.cipher.decrypt(user.totp_secret) == result.secret

    async def test_confirmar_con_codigo_valido_activa(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        result = await EnableTwoFactorUseCase(deps.security).execute(
            EnableTwoFactorCommand(user_id="u1")
        )
        code = pyotp.TOTP(result.secret).now()
        await ConfirmTwoFactorUseCase(deps.security).execute(
            ConfirmTwoFactorCommand(user_id="u1", code=code)
        )
        user = await deps.repository.get("u1")
        assert user is not None and user.totp_enabled is True

    async def test_confirmar_con_codigo_invalido_rechaza(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        await EnableTwoFactorUseCase(deps.security).execute(EnableTwoFactorCommand(user_id="u1"))
        with pytest.raises(TwoFactorInvalidError):
            await ConfirmTwoFactorUseCase(deps.security).execute(
                ConfirmTwoFactorCommand(user_id="u1", code="000000")
            )

    async def test_confirmar_sin_enable_rechaza(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        with pytest.raises(TwoFactorNotEnabledError):
            await ConfirmTwoFactorUseCase(deps.security).execute(
                ConfirmTwoFactorCommand(user_id="u1", code="000000")
            )


class TestLoginWith2fa:
    async def test_login_exige_segundo_factor(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        await _enable(deps)
        with pytest.raises(TwoFactorRequiredError) as exc_info:
            await LoginUseCase(deps.deps).execute(LoginCommand(username="alice", password="pass"))
        assert exc_info.value.context is not None
        assert "temp_token" in exc_info.value.context

    async def test_verify_2fa_completa_el_login(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        secret = await _enable(deps)
        code = pyotp.TOTP(secret).now()
        temp = deps.tokens.create_temp_token("u1")
        result = await VerifyTwoFactorLoginUseCase(deps.security).execute(
            VerifyTwoFactorLoginCommand(temp_token=temp, code=code)
        )
        assert result.access_token.startswith("access.u1.")
        assert result.refresh_token.startswith("refresh.")
        assert result.identity.id == "u1"

    async def test_verify_2fa_con_codigo_invalido_rechaza(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        await _enable(deps)
        temp = deps.tokens.create_temp_token("u1")
        with pytest.raises(TwoFactorInvalidError):
            await VerifyTwoFactorLoginUseCase(deps.security).execute(
                VerifyTwoFactorLoginCommand(temp_token=temp, code="000000")
            )

    async def test_verify_2fa_con_backup_code_funciona_y_lo_consume(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        result = await EnableTwoFactorUseCase(deps.security).execute(
            EnableTwoFactorCommand(user_id="u1")
        )
        await ConfirmTwoFactorUseCase(deps.security).execute(
            ConfirmTwoFactorCommand(user_id="u1", code=pyotp.TOTP(result.secret).now())
        )
        backup = result.backup_codes[0]
        temp = deps.tokens.create_temp_token("u1")
        login = await VerifyTwoFactorLoginUseCase(deps.security).execute(
            VerifyTwoFactorLoginCommand(temp_token=temp, code=backup)
        )
        assert login.access_token
        user = await deps.repository.get("u1")
        assert user is not None and user.backup_codes is not None
        remaining = deps.cipher.decrypt(user.backup_codes)
        assert backup not in remaining

    async def test_temp_token_invalido_rechaza(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        await _enable(deps)
        with pytest.raises(TokenInvalidError):
            await VerifyTwoFactorLoginUseCase(deps.security).execute(
                VerifyTwoFactorLoginCommand(temp_token="basura", code="000000")
            )


class TestBackupCodesRegen:
    async def test_regenerar_requiere_2fa_activo(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        with pytest.raises(TwoFactorNotEnabledError):
            await RegenerateBackupCodesUseCase(deps.security).execute(
                RegenerateBackupCodesCommand(user_id="u1")
            )

    async def test_regenerar_devuelve_nuevos_codes(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        secret = await _enable(deps)
        await ConfirmTwoFactorUseCase(deps.security).execute(
            ConfirmTwoFactorCommand(user_id="u1", code=pyotp.TOTP(secret).now())
        )
        codes = await RegenerateBackupCodesUseCase(deps.security).execute(
            RegenerateBackupCodesCommand(user_id="u1")
        )
        assert len(codes) == 10


class TestDisableTwoFactor:
    async def test_desactivar_requiere_2fa_activo(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        with pytest.raises(TwoFactorNotEnabledError):
            await DisableTwoFactorUseCase(deps.security).execute(
                DisableTwoFactorCommand(user_id="u1")
            )

    async def test_desactivar_limpia_secreto_backup_codes_y_flag(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        result = await EnableTwoFactorUseCase(deps.security).execute(
            EnableTwoFactorCommand(user_id="u1")
        )
        await ConfirmTwoFactorUseCase(deps.security).execute(
            ConfirmTwoFactorCommand(user_id="u1", code=pyotp.TOTP(result.secret).now())
        )
        loaded = await deps.repository.get("u1")
        assert loaded is not None and loaded.totp_enabled is True

        await DisableTwoFactorUseCase(deps.security).execute(
            DisableTwoFactorCommand(user_id="u1")
        )
        user = await deps.repository.get("u1")
        assert user is not None
        assert user.totp_enabled is False
        assert user.totp_secret is None
        assert user.backup_codes is None


class TestTwoFactorStatus:
    async def test_status_refleja_habilitado_y_deshabilitado(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        assert await GetTwoFactorStatusUseCase(deps.security).execute("u1") is False

        result = await EnableTwoFactorUseCase(deps.security).execute(
            EnableTwoFactorCommand(user_id="u1")
        )
        await ConfirmTwoFactorUseCase(deps.security).execute(
            ConfirmTwoFactorCommand(user_id="u1", code=pyotp.TOTP(result.secret).now())
        )
        assert await GetTwoFactorStatusUseCase(deps.security).execute("u1") is True

        await DisableTwoFactorUseCase(deps.security).execute(
            DisableTwoFactorCommand(user_id="u1")
        )
        assert await GetTwoFactorStatusUseCase(deps.security).execute("u1") is False


class TestApiKeys:
    async def test_crear_devuelve_material_y_guarda_hash(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        created = await CreateApiKeyUseCase(deps.security).execute(
            CreateApiKeyCommand(user_id="u1", name="ci", scopes=("server.list",))
        )
        assert created.material.startswith("sk_live_")
        assert len(created.material) == len("sk_live_") + 64
        stored = await deps.api_keys.get_by_hash(hash_api_key(created.material))
        assert stored is not None
        assert stored.name == "ci"
        assert stored.scopes == ("server.list",)

    async def test_listar_y_revocar(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        first = await CreateApiKeyUseCase(deps.security).execute(
            CreateApiKeyCommand(user_id="u1", name="a")
        )
        await CreateApiKeyUseCase(deps.security).execute(
            CreateApiKeyCommand(user_id="u1", name="b")
        )
        listed = await ListApiKeysUseCase(deps.security).execute("u1")
        assert len(listed) == 2
        assert all(not hasattr(key, "material") for key in listed)
        await RevokeApiKeyUseCase(deps.security).execute(
            RevokeApiKeyCommand(user_id="u1", key_id=first.key.id)
        )
        listed = await ListApiKeysUseCase(deps.security).execute("u1")
        assert len(listed) == 1

    async def test_rotar_invalida_el_material_anterior(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        created = await CreateApiKeyUseCase(deps.security).execute(
            CreateApiKeyCommand(user_id="u1", name="a")
        )
        rotated = await RotateApiKeyUseCase(deps.security).execute(
            RotateApiKeyCommand(user_id="u1", key_id=created.key.id)
        )
        assert rotated.material != created.material
        assert await deps.api_keys.get_by_hash(hash_api_key(created.material)) is None
        assert await deps.api_keys.get_by_hash(hash_api_key(rotated.material)) is not None

    async def test_resolver_devuelve_key_y_toca_last_used(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        created = await CreateApiKeyUseCase(deps.security).execute(
            CreateApiKeyCommand(user_id="u1", name="a")
        )
        resolver = ResolveApiKeyUseCase(deps.security)
        key = await resolver.resolve(created.material)
        assert key is not None
        assert key.user_id == "u1"
        stored = await deps.api_keys.get_by_hash(hash_api_key(created.material))
        assert stored is not None and stored.last_used_at == NOW

    async def test_resolver_desconocido_devuelve_none(self) -> None:
        deps = Deps()
        await deps.repository.save(make_user())
        resolver = ResolveApiKeyUseCase(deps.security)
        assert await resolver.resolve("sk_live_zzzzzz") is None


async def _enable(deps: Deps) -> str:
    result = await EnableTwoFactorUseCase(deps.security).execute(
        EnableTwoFactorCommand(user_id="u1")
    )
    await ConfirmTwoFactorUseCase(deps.security).execute(
        ConfirmTwoFactorCommand(user_id="u1", code=pyotp.TOTP(result.secret).now())
    )
    return result.secret
