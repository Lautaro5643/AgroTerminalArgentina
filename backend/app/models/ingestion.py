"""Modelos de trazabilidad de la ingesta de datos.

Son independientes de la fuente: sirven para cualquier proveedor (BCR, A3,
USDA, etc.). Permiten reconstruir de dónde vino cada dato, preservar el
original tal como llegó y registrar los errores de importación.

Las tablas de precios normalizados se agregan después, cuando exista una
respuesta real de cada fuente y se conozcan sus campos.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

IMPORT_STATUSES = ("running", "succeeded", "partial", "failed")


class DataSource(Base):
    """Proveedor de datos (por ejemplo, BCR GIX)."""

    __tablename__ = "data_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    # Condiciones de uso / licencia tal como las informó el proveedor.
    license_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ImportBatch(Base):
    """Una ejecución de importación desde una fuente."""

    __tablename__ = "import_batch"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'partial', 'failed')",
            name="ck_import_batch_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), server_default="running")
    # Parámetros usados (por ejemplo, rango de fechas consultado).
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Versión del proceso de normalización aplicado a este lote.
    normalization_version: Mapped[str | None] = mapped_column(String(50))
    rows_received: Mapped[int] = mapped_column(Integer, server_default="0")
    rows_loaded: Mapped[int] = mapped_column(Integer, server_default="0")


class RawRecord(Base):
    """Registro original, exactamente como lo entregó la fuente.

    Nunca se modifica. La normalización crea registros derivados que apuntan
    a este.
    """

    __tablename__ = "raw_record"
    __table_args__ = (
        # Evita duplicar un registro idéntico de la misma fuente.
        UniqueConstraint("source_id", "payload_hash", name="uq_raw_record_source_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batch.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_source.id"))
    payload:Mapped[dict[str, Any]] = mapped_column(JSONB)
    # SHA-256 (hex) del payload serializado de forma canónica.
    payload_hash: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ImportIssue(Base):
    """Error o advertencia registrado durante una importación."""

    __tablename__ = "import_error"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batch.id"), index=True)
    raw_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_record.id"), index=True
    )
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
