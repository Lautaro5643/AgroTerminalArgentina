"""Ingesta de datos: aterrizaje de registros originales de cualquier fuente."""

from app.ingestion.importer import (
    ImportResult,
    SourceNotFoundError,
    payload_hash,
    run_import,
)

__all__ = ["ImportResult", "SourceNotFoundError", "payload_hash", "run_import"]
