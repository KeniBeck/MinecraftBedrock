"""Modelos SQLAlchemy del módulo Notification (prefijo ``noti_*``).

``NotificationLogRow`` es el ``EventLog`` append-only del gateway (§15.8): un
registro por evento difundido, numerado con ``seq`` global monótono e indexado
por ``(scope, server_id, seq)`` para resume eficiente. Sin FKs a otros módulos
(bounded contexts, mismo criterio que los demás).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class NotificationLogRow(Base):
    """Registro inmutable de un evento difundido (append-only)."""

    __tablename__ = "noti_event_log"
    __table_args__ = (Index("ix_noti_event_log_scope_seq", "scope", "server_id", "seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    server_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
