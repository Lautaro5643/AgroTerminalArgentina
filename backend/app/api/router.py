"""Router principal de la API."""

from fastapi import APIRouter

api_router = APIRouter()


@api_router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Indica que la aplicación está viva.

    No consulta la base de datos: solo confirma que FastAPI responde.
    """
    return {"status": "ok"}
