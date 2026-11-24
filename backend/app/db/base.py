"""Clase base de los modelos de SQLAlchemy.

Todos los modelos de la aplicación heredan de Base. Alembic la usa para
detectar las tablas y generar migraciones.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
