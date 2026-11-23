import pytest
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_engine


@pytest.fixture
def db_session():
    """Sesión contra PostgreSQL real dentro de una transacción que se deshace.

    Nada de lo que hagan los tests queda en la base. Si la base no está
    disponible o faltan las migraciones, el test se saltea.
    """
    try:
        engine = get_engine()
        with engine.connect() as probe:
            tiene_tablas = inspect(probe).has_table("raw_record")
    except (ValidationError, SQLAlchemyError):
        pytest.skip("Sin base de datos disponible (¿docker compose up -d y .env?)")

    if not tiene_tablas:
        pytest.skip("Faltan las tablas: ejecutar 'alembic upgrade head'")

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
