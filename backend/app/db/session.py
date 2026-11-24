"""Conexión a PostgreSQL y manejo de sesiones.

El engine se crea la primera vez que se necesita (no al importar el módulo),
así los tests y las herramientas que no usan la base no requieren un .env.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Crea (una sola vez) el engine de conexión a PostgreSQL."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Crea (una sola vez) la fábrica de sesiones."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: entrega una sesión y la cierra al terminar."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
