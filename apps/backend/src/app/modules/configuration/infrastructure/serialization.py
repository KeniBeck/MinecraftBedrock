"""Serialización del dominio Configuration ↔ filas (test sin BBDD)."""

from __future__ import annotations

from typing import Any

from app.modules.configuration.domain.config_profile import ConfigChange, ConfigProfile
from app.modules.configuration.infrastructure.models import ConfigHistoryRow, ConfigProfileRow


def profile_to_row(profile: ConfigProfile) -> dict[str, Any]:
    """Proyección de ``ConfigProfile`` a los campos de ``ConfigProfileRow``."""
    return {
        "server_id": profile.server_id,
        "properties": dict(profile.properties),
        "version": profile.version,
        "config_rev": profile.config_rev,
        "applied": dict(profile.applied) if profile.applied is not None else None,
        "applied_at": profile.applied_at,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def profile_from_row(row: ConfigProfileRow) -> ConfigProfile:
    """Reconstruye ``ConfigProfile`` desde una fila."""
    return ConfigProfile(
        server_id=row.server_id,
        properties=dict(row.properties),
        version=row.version,
        config_rev=row.config_rev,
        applied=dict(row.applied) if row.applied is not None else None,
        applied_at=row.applied_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def change_from_row(row: ConfigHistoryRow) -> ConfigChange:
    """Reconstruye ``ConfigChange`` desde una fila del historial."""
    return ConfigChange(
        server_id=row.server_id,
        config_rev=row.config_rev,
        properties=dict(row.properties),
        version=row.version,
        changed_at=row.changed_at,
        actor_id=row.actor_id,
    )
