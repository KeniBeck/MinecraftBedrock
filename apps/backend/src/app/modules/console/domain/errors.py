"""Errores del módulo Console (Blueprint §11.1, códigos ``CONSOLE.*``).

La taxonomía ``CONSOLE.*`` vive en el kernel compartido (§11.1) porque la
consume también la frontera de infraestructura (streaming). El módulo la
re-exporta para ofrecer un único punto de importación, igual que Server expone
sus ``SERVER.*`` en ``domain/errors.py``.
"""

from __future__ import annotations

from app.kernel.errors import (
    CommandRejectedError,
    ConsoleBusyError,
    ConsoleError,
    ConsoleUnavailableError,
    ServerOfflineError,
    StdinWriteError,
)

__all__ = [
    "CommandRejectedError",
    "ConsoleBusyError",
    "ConsoleError",
    "ConsoleUnavailableError",
    "ServerOfflineError",
    "StdinWriteError",
]
