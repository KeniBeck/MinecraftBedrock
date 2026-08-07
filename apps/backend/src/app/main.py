"""Entry point ASGI.

Ejecución: ``uv run uvicorn app.main:app --reload``.
"""

from app.bootstrap.main import create_app

app = create_app()
