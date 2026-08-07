"""Entorno de migraciones Alembic (Fase A paso 2, async sobre psycopg).

La URL de conexión se toma de ``alembic.ini`` y se sobrescribe desde
``Settings`` (carga ``.env`` igual que la aplicación; Fase C paso 8) o por la
variable de entorno ``BEDROCK_PANEL_DATABASE_URL``. Los modelos se registran por
módulo en ``target_metadata`` conforme se implementen (Server, Console, IAM).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Registro de modelos por módulo (Bluepring §10.5: tablas con prefijo).
import app.modules.console.infrastructure.models  # noqa: F401
import app.modules.iam.infrastructure.models  # noqa: F401
import app.modules.server.infrastructure.models  # noqa: F401
from app.bootstrap.config import get_settings
from app.infrastructure.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Corrección (Fase C paso 8): la URL se lee de ``Settings``, que carga ``.env``
# igual que la aplicación (misma fuente de verdad, sin duplicar parseo).
# Sobrescribe ``sqlalchemy.url`` de ``alembic.ini``; ``alembic upgrade head``
# funciona sin inyección manual de variables.
database_url = get_settings().database_url
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo offline (genera SQL sin conexión)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configura el contexto sobre una conexión concreta y migra."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Ejecuta migraciones online con un motor async (psycopg)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
