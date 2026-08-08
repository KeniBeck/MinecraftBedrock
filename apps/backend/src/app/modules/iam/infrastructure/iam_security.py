"""Repositorios Postgres de permisos y API keys del módulo IAM (Fase H paso 18).

``PostgresPermissionRepository`` lee la matriz sembrada en ``iam_permissions`` +
``iam_role_permissions``. ``PostgresApiKeyStore`` persiste API keys (solo el
hash del material). Ambos implementan los ports de dominio/aplicación; la
siembra del catálogo se hace de forma idempotente en ``seed_catalog``.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.iam.application.ports import (
    ApiKey,
)
from app.modules.iam.domain.errors import SecretCipherError
from app.modules.iam.domain.permissions import (
    ALL_PERMISSIONS,
    PERMISSIONS_SEED,
    ROLE_PERMISSIONS,
    PermissionCode,
)
from app.modules.iam.domain.role import BuiltinRole
from app.modules.iam.infrastructure.models import (
    IamApiKeyRow,
    IamPermissionRow,
    IamRolePermissionRow,
)


class FernetSecretCipher:
    """Cifra secretos en reposo con Fernet (clave de Settings ``iam.encryption_key``)."""

    def __init__(self, key: str) -> None:
        try:
            from cryptography.fernet import Fernet, InvalidToken

            self._fernet = Fernet(key)
            self._invalid_token = InvalidToken
        except (ValueError, ImportError) as exc:  # clave no Fernet / lib ausente
            raise SecretCipherError(
                "Clave de cifrado inválida o librería cryptography ausente",
                context={"reason": str(exc)},
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            token = self._fernet.decrypt(ciphertext.encode("utf-8"))
        except self._invalid_token as exc:
            raise SecretCipherError("Ciphertext inválido o clave incorrecta") from exc
        return token.decode("utf-8")


class PyotpTotpService:
    """Verifica códigos TOTP y gestiona backup codes (Fase H paso 18)."""

    def __init__(self, issuer: str = "BedrockPanel") -> None:
        self._issuer = issuer

    def generate_secret(self) -> str:
        import pyotp

        return pyotp.random_base32()

    def provisioning_uri(self, secret: str, username: str) -> str:
        import pyotp

        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=username, issuer_name=self._issuer)

    def verify(self, secret: str, code: str) -> bool:
        import pyotp

        return pyotp.TOTP(secret).verify(code, valid_window=1)

    def generate_backup_codes(self) -> tuple[str, ...]:
        return tuple(secrets.token_hex(4) for _ in range(10))

    def verify_backup_code(self, code: str, codes: tuple[str, ...]) -> bool:
        return code in codes


def generate_api_key_material() -> tuple[str, str]:
    """Devuelve ``(material, hash)``: ``sk_live_`` + 32 hex y su SHA-256."""
    raw = f"sk_live_{secrets.token_hex(32)}"
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hash_api_key(raw: str) -> str:
    """SHA-256 del material de una API key (para lookup/rotación)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class PostgresPermissionRepository:
    """Matriz de permisos persistida (catalogo ``iam_permissions``)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_permissions(self) -> Sequence[PermissionCode]:
        async with self._session_factory() as session:
            result = await session.execute(select(IamPermissionRow).order_by(IamPermissionRow.code))
            rows = result.scalars().all()
        return [PermissionCode(code=row.code, category=row.category) for row in rows]

    async def permissions_for_role(self, role: BuiltinRole) -> frozenset[str]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(IamRolePermissionRow.permission_code).where(
                    IamRolePermissionRow.role == role.value
                )
            )
            codes = frozenset(row[0] for row in result.all())
        # Fallback a la matriz estática: si la migración no sembró el catálogo
        # (p. ej. base recién creada), la autorización no se degrada.
        return codes or ROLE_PERMISSIONS.get(role, frozenset())

    async def seed_catalog(self) -> None:
        """Sembra el catálogo base y la matriz si la tabla está vacía (idempotente)."""
        async with self._session_factory() as session:
            count = await session.scalar(select(IamPermissionRow.code).limit(1))
            if count is not None:
                return
            session.add_all(
                IamPermissionRow(
                    code=permission.code,
                    category=permission.category,
                    description=f"{permission.code} ({permission.category})",
                )
                for permission in PERMISSIONS_SEED
            )
            for role in BuiltinRole:
                codes = await self._role_seed_codes(role)
                session.add_all(
                    IamRolePermissionRow(role=role.value, permission_code=code) for code in codes
                )
            await session.commit()

    async def _role_seed_codes(self, role: BuiltinRole) -> frozenset[str]:
        if role in (BuiltinRole.SUPER_ADMIN, BuiltinRole.ADMIN):
            return ALL_PERMISSIONS

        return ROLE_PERMISSIONS[role]


class PostgresApiKeyStore:
    """Persistencia de API keys en la tabla ``iam_api_keys``."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, key: ApiKey) -> None:
        row = IamApiKeyRow(
            id=key.id,
            user_id=key.user_id,
            name=key.name,
            key_hash=key.key_hash,
            scopes=list(key.scopes),
            last_used_at=key.last_used_at,
            created_at=key.created_at,
            expires_at=key.expires_at,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(IamApiKeyRow).where(IamApiKeyRow.key_hash == key_hash)
            )
            row = result.scalar_one_or_none()
        return self._from_row(row) if row is not None else None

    async def list_for_user(self, user_id: str) -> list[ApiKey]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(IamApiKeyRow).where(IamApiKeyRow.user_id == user_id)
            )
            rows = result.scalars().all()
        return [self._from_row(row) for row in rows]

    async def revoke(self, key_id: str, user_id: str) -> None:
        stmt = delete(IamApiKeyRow).where(
            IamApiKeyRow.id == key_id, IamApiKeyRow.user_id == user_id
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def rotate(self, key_id: str, user_id: str, key_hash: str) -> None:
        stmt = (
            update(IamApiKeyRow)
            .where(IamApiKeyRow.id == key_id, IamApiKeyRow.user_id == user_id)
            .values(key_hash=key_hash, last_used_at=None)
        )
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def touch(self, key_id: str, at: datetime) -> None:
        stmt = update(IamApiKeyRow).where(IamApiKeyRow.id == key_id).values(last_used_at=at)
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    @staticmethod
    def _from_row(row: IamApiKeyRow) -> ApiKey:
        return ApiKey(
            id=row.id,
            user_id=row.user_id,
            name=row.name,
            key_hash=row.key_hash,
            scopes=tuple(str(scope) for scope in row.scopes or []),
            last_used_at=row.last_used_at,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )
