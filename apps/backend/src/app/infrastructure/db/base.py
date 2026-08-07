"""Base declarativa SQLAlchemy para los modelos por módulo (Blueprint §10.5).

Cada módulo definirá sus modelos con prefijo de tabla; Alembic usará esta
metadata como target de autogenerate.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa del panel (tables con prefijo de módulo)."""
