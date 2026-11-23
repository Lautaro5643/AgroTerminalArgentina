import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings


@pytest.fixture(scope="session")
def db_engine():
    """Engine de pruebas. Se intenta conectar UNA sola vez y rápido.

    Si la base no responde en pocos segundos, o faltan las tablas, todos los
    tests que la necesitan se saltean (sin reintentar test por test).
    """
    try:
        engine = create_engine(
            get_settings().database_url,
            connect_args={"connect_timeout": 3},
        )
        with engine.connect() as probe:
            tiene_tablas = inspect(probe).has_table("raw_record")
    except (ValidationError, SQLAlchemyError):
        pytest.skip("Sin base de datos disponible (¿docker compose up -d y .env?)")

    if not tiene_tablas:
        pytest.skip("Faltan las tablas: ejecutar 'alembic upgrade head'")

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Sesión contra PostgreSQL real dentro de una transacción que se deshace.

    Nada de lo que hagan los tests queda en la base.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
