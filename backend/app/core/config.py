"""Configuración de la aplicación.

Lee las variables desde el archivo .env de la raíz del proyecto (o desde
variables de entorno reales). Nunca guardar contraseñas en el código.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# backend/app/core/config.py -> la raíz del proyecto está 3 niveles arriba.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Variables de configuración. Los nombres coinciden con las del .env."""

    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_port: int = 5433
    postgres_host: str = "127.0.0.1"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> URL:
        """URL de conexión a PostgreSQL para SQLAlchemy (driver psycopg 3).

        Se arma con URL.create para que caracteres especiales en la
        contraseña no rompan la conexión.
        """
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración (se lee una sola vez)."""
    return Settings()
