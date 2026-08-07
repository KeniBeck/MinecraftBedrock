"""Factoría de la aplicación FastAPI con el wiring de módulos (TDD §16).

Paso de cierre (Fase C/D1): la app registra los routers de IAM, Server y
Console (vertical slice ``modules/*/api``) bajo ``Settings.api_prefix``, el
mapeo central de errores y el ciclo de vida del ``Database`` (dispose en
shutdown). ``create_app`` acepta un ``Container`` opcional para que los tests
de integración HTTP inyecten uno con dobles (mismo criterio que las fases
previas: la base real corre sin inyección).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap.config import get_settings
from app.bootstrap.container import Container, build_container
from app.bootstrap.errors import register_exception_handlers
from app.kernel.logging import configure_logging
from app.modules.console.api.router import router as console_router
from app.modules.iam.api.router import router as iam_router
from app.modules.monitoring.api.router import router as monitoring_router
from app.modules.server.api.router import router as server_router


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    poller = app.state.container.monitoring_poller
    if poller is not None:
        await poller.start()
    try:
        yield
    finally:
        if poller is not None:
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

    _register_root(app)
    return app


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
