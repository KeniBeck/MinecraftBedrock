"""Entry point ASGI.

Punto de entrada histórica: la factoría vive en ``bootstrap/main.py`` (paso de
cierre de presentación); ``create_app`` se re-exporta para compatibilidad.

Ejecución: ``uv run uvicorn app.main:app --reload``.
"""

from __future__ import annotations

from app.bootstrap.main import create_app

__all__ = ["create_app"]
