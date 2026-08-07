"""Política de logging (Blueprint §12).

Configuración base del logging estructurado con niveles por convención
(§12.3). Todo componente (incluida la infraestructura) obtiene sus loggers
desde ``get_logger`` para depender exclusivamente del sistema de logging
definido por el Kernel. El formateador JSON definitivo se añadirá en
infraestructura.
"""

from __future__ import annotations

import logging
import sys


def configure_logging(*, level: str = "INFO", debug: bool = False) -> None:
    """Configura el logging de raíz del panel.

    Args:
        level: Nivel por defecto (INFO/WARN/DEBUG/…).
        debug: Si es ``True``, fuerza el nivel DEBUG.
    """
    effective = "DEBUG" if debug else level
    logging.basicConfig(
        level=getattr(logging, effective.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger del panel bajo el namespace ``app.*``.

    Todo componente obtiene sus loggers desde aquí: centraliza la política de
    niveles y formato (§12) y evita que cada módulo configure su propio logger.
    """
    if name.startswith("app."):
        return logging.getLogger(name)
    return logging.getLogger(f"app.{name}")
