"""Contrato ``SettingsPort`` (Blueprint §1.2, §3.13).

Lectura de configuración global del panel. Lo implementa el módulo
``Settings``; ningún módulo lee config global fuera de este puerto.
"""

from __future__ import annotations

from typing import Any, Protocol


class SettingsPort(Protocol):
    """Acceso de solo lectura a la configuración global."""

    def get(self, key: str, default: Any = None) -> Any:
        """Devuelve el valor del ajuste ``key`` o ``default``."""
