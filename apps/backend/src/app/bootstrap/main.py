"""Factoría de la aplicación FastAPI con el wiring de módulos (TDD §16).

Paso de cierre (Fase C/D1): la app registra los routers de IAM, Server y
Console (vertical slice ``modules/*/api``) bajo ``Settings.api_prefix``, el
mapeo central de errores y el ciclo de vida del ``Database`` (dispose en
shutdown). ``create_app`` acepta un ``Container`` opcional para que los tests
de integración HTTP inyecten uno con dobles (mismo criterio que las fases
previas: la base real corre sin inyección).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap.config import get_settings
from app.bootstrap.container import Container, build_container
from app.bootstrap.errors import register_exception_handlers
from app.kernel.logging import configure_logging
from app.modules.backup.api.router import router as backup_router
from app.modules.console.api.router import router as console_router
from app.modules.iam.api.router import router as iam_router
from app.modules.monitoring.api.router import router as monitoring_router
from app.modules.notification.api.router import router as notification_router
from app.modules.permission.api.router import router as permission_router
from app.modules.player.api.router import router as player_router
from app.modules.scheduler.api.router import router as scheduler_router
from app.modules.server.api.router import router as server_router
from app.modules.settings.api.router import router as settings_router
from app.modules.template.api.router import router as template_router
from app.modules.world.api.router import router as world_router


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    monitor = app.state.container.monitoring_poller
    scheduler = app.state.container.scheduler_poller
    pollers = [poller for poller in (monitor, scheduler) if poller is not None]
    reconciler = app.state.container.console_stream_reconciler
    if reconciler is not None:
        await reconciler.reconcile()
    await app.state.container.settings_service.reload()
    await _bootstrap_admin(app)
    for poller in pollers:
        await poller.start()
    try:
        yield
    finally:
        for poller in pollers:
            await poller.stop()
        await app.state.container.database.dispose()


def create_app(container: Container | None = None) -> FastAPI:
    """Construye la aplicación FastAPI con los routers de los módulos.

    Sin ``container`` se compone el contenedor de producción (``build_container``).
    """
    settings = get_settings()
    configure_logging(level=settings.log_level, debug=settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=_lifespan,
    )
    app.state.container = container if container is not None else build_container()

    register_exception_handlers(app)

    api_prefix = settings.api_prefix
    app.include_router(iam_router, prefix=api_prefix)
    app.include_router(server_router, prefix=api_prefix)
    app.include_router(console_router, prefix=api_prefix)
    app.include_router(monitoring_router, prefix=api_prefix)
    app.include_router(world_router, prefix=api_prefix)
    app.include_router(player_router, prefix=api_prefix)
    app.include_router(permission_router, prefix=api_prefix)
    app.include_router(backup_router, prefix=api_prefix)
    app.include_router(scheduler_router, prefix=api_prefix)
    app.include_router(template_router, prefix=api_prefix)
    app.include_router(notification_router, prefix=api_prefix)
    app.include_router(settings_router, prefix=api_prefix)

    _register_root(app)
    return app


async def _bootstrap_admin(app: FastAPI) -> None:
    """Bootstrap de super_admin de primer arranque (producción).

    Si ``bootstrap_admin_username``/``bootstrap_admin_password`` están
    definidos en el entorno, crea (idempotente) un super_admin. Defensivo: un
    fallo de bootstrap no debe tumbar el arranque del panel.
    """
    settings = get_settings()
    if not settings.bootstrap_admin_username or not settings.bootstrap_admin_password:
        return
    iam = app.state.container.iam_facade
    try:
        await iam.ensure_bootstrap_admin(
            settings.bootstrap_admin_username,
            settings.bootstrap_admin_password,
            settings.bootstrap_admin_display_name,
        )
        logging.getLogger(__name__).info(
            "Bootstrap admin listo: %s", settings.bootstrap_admin_username
        )
    except Exception:  # pragma: no cover - defensivo
        logging.getLogger(__name__).exception(
            "Fallo al crear el bootstrap admin (se omite): %s",
            settings.bootstrap_admin_username,
        )


def _register_root(app: FastAPI) -> None:
    """Endpoint raíz: identidad y estado del panel (requisito del esqueleto)."""

    @app.get("/", tags=["meta"], summary="Información del panel")
    def root() -> dict[str, str]:
        settings = get_settings()
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "ok",
        }
