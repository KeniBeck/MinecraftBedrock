"""Contrato ``SettingsPort`` (Blueprint §1.2, §3.13) y repositorio (Fase H paso 19).

Lectura de configuración global del panel. ``SettingsPort`` es el acceso de
solo lectura que consumen todos los módulos; ``SettingsRepositoryPort`` es la
persistencia (tabla ``settings``) que alimenta el ``SettingsService``. Ningún
módulo lee config global fuera de este puerto.
"""

from __future__ import annotations

from typing import Any, Protocol


class SettingsPort(Protocol):
    """Acceso de solo lectura a la configuración global."""

    def get(self, key: str, default: Any = None) -> Any:
        """Devuelve el valor del ajuste ``key`` o ``default``."""


class SettingsRepositoryPort(Protocol):
    """Persistencia de ajustes (tabla ``settings``)."""

    async def get(self, key: str) -> Any | None:
        """Devuelve el valor del ajuste o ``None``."""

    async def set(
        self,
        key: str,
        value: Any,
        category: str,
        description: str | None,
        updated_by: str,
    ) -> None:
        """Inserta o actualiza el ajuste (upsert por ``key``)."""

    async def delete(self, key: str) -> None:
        """Elimina el ajuste (para resetear al default)."""

    async def set_many(
        self,
        values: dict[str, Any],
        description: str | None,
        updated_by: str,
    ) -> None:
        """Actualiza varios ajustes de forma atómica (una transacción)."""

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Devuelve los valores de un conjunto de claves (existentes)."""

    async def list_by_category(self, category: str) -> dict[str, Any]:
        """Devuelve los ajustes de una categoría."""

    async def get_all(self) -> dict[str, Any]:
        """Devuelve todos los ajustes (clave → valor)."""

    async def list_full(self) -> list[dict[str, Any]]:
        """Devuelve todos los ajustes con metadata (key, category, description)."""
