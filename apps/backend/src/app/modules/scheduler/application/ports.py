"""Puertos de entrada de la aplicación Scheduler (Blueprint §3.9, §4.3).

Scheduler no reimplementa lo que ya hacen otros módulos: los facades Server,
Backup y Console actúan como **ejecutores** vía puertos estructurales. Solo se
acota la superficie necesaria:

- ``BackupRunner`` — dispara un snapshot (``BackupFacade.create_backup``).
- ``ServerRunner`` — reinicia un servidor (``ServerFacade.restart``).

Para tareas ``command`` no hace falta puerto: Scheduler publica
``TASK.STARTED`` con ``{"server_id", "commands"}`` y el ``TaskStartedHandler``
de Console ejecuta.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.backup.application.commands import CreateBackupCommand
from app.modules.backup.application.results import BackupView
from app.modules.server.application.commands import RestartServerCommand
from app.modules.server.application.results import ServerView


class BackupRunner(Protocol):
    """Superficie de Backup que Scheduler usa para tareas ``backup``."""

    async def create_backup(self, cmd: CreateBackupCommand) -> BackupView:
        """Snapshot de un mundo."""


class ServerRunner(Protocol):
    """Superficie de Server que Scheduler usa para tareas ``restart``."""

    async def restart(self, cmd: RestartServerCommand) -> ServerView:
        """Reinicia el servidor."""
