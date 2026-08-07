"""Modelos SQLAlchemy del módulo IAM (Fase C paso 8, tablas ``iam_*``).

Mapeo físico según technical-design §15.1 (mínimo viable): ``iam_users``,
``iam_user_roles`` (rol global por nombre), ``iam_server_memberships`` (ACL),
``iam_sessions`` (refresh tokens revocables) e ``iam_audit_logs`` (log básico,
sin encadenado de hash — eso es Fase H). Sin FKs a ``server_servers`` para
mantener los bounded contexts desacoplados (decisiones documentadas).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class IamUserRow(Base):
    """Cuenta de usuario del panel."""

    __tablename__ = "iam_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IamUserRoleRow(Base):
    """Rol global de un usuario (N:M implícita por nombre, sin catálogo Fase H)."""

    __tablename__ = "iam_user_roles"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), primary_key=True)


class IamServerMembershipRow(Base):
    """Membresía (ACL) de un usuario sobre un servidor."""

    __tablename__ = "iam_server_memberships"

    server_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)


class IamSessionRow(Base):
    """Sesión de refresh token (revocable, technical-design §14.1)."""

    __tablename__ = "iam_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ua: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IamAuditLogRow(Base):
    """Registro de auditoría (append-only; sin hash-chain en este paso)."""

    __tablename__ = "iam_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict
    )
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ua: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
