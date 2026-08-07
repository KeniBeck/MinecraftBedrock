"""Comandos tipados de los use cases del módulo Backup (CQRS, Blueprint §4.7)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateBackupCommand:
    """Crear un backup manual (o ``protected`` para pre-restore/pre-upgrade)."""

    server_id: str
    world_name: str
    protected: bool = False
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class RestoreBackupCommand:
    """Restaurar un backup sobre ``worlds/<world_name>/`` (§8.6)."""

    backup_id: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class PruneBackupCommand:
    """Limpieza por retención: conserva los N más recientes por mundo (y los protegidos)."""

    server_id: str
    keep_last_n: int = 10
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class ValidateBackupCommand:
    """Valida la integridad de un artefacto (checksum + manifiesto)."""

    backup_id: str
    actor_id: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteBackupCommand:
    """Elimina un backup individual (artefacto + registro; no los protegidos)."""

    backup_id: str
    actor_id: str | None = None
