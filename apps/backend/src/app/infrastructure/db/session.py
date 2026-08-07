"""Motor y fábrica de sesiones asíncronas de Postgres (Fase A paso 2).

Soporte de SQLAlchemy 2.0 async sobre ``psycopg`` (v3), que sirve tanto para
el motor síncrono de Alembic como para el asíncrono de la aplicación (misma
URL ``postgresql+psycopg://``). La conexión es perezosa: construir el
``Database`` no abre socket; la primera operación lo hace.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Parámetros de conexión y pool (Bluepring §2 paso 2)."""

    url: str
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800
    echo: bool = False


class Database:
    """Ciclo de vida del engine async y la ``async_sessionmaker`` del panel."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings
        self._engine: AsyncEngine = create_async_engine(
            settings.url,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_timeout=settings.pool_timeout,
            pool_recycle=settings.pool_recycle,
            pool_pre_ping=True,
            echo=settings.echo,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        """Motor async (conexión perezosa)."""
        return self._engine

    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Fábrica de sesiones por repositorio (una sesión por operación)."""
        return self._session_factory

    async def dispose(self) -> None:
        """Cierra el pool; idempotente y seguro para el shutdown de la app."""
        await self._engine.dispose()
