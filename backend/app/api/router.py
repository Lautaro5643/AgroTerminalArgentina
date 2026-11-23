"""Router principal de la API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db

api_router = APIRouter()


@api_router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Indica que la aplicación está viva.

    No consulta la base de datos: solo confirma que FastAPI responde.
    """
    return {"status": "ok"}


@api_router.get("/health/db", tags=["system"])
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """Indica si la aplicación puede conectarse a PostgreSQL.

    Responde 503 si la base no está disponible. No expone el detalle del
    error (podría incluir datos de la conexión).
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503, detail="Base de datos no disponible"
        ) from exc
    return {"status": "ok", "database": "ok"}
