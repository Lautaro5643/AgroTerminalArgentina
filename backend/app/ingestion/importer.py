"""Importador genérico de registros originales.

No conoce ninguna fuente en particular. Recibe registros ya separados (un
diccionario por registro) y se encarga de:

- abrir un lote en ``import_batch``;
- guardar cada registro original, sin modificar, en ``raw_record``;
- evitar duplicados por (fuente, hash del contenido);
- registrar los registros inválidos en ``import_error``;
- cerrar el lote con contadores y un estado.

Cada fuente necesita un adaptador propio que se conecte, parta la respuesta
en registros y los entregue a ``run_import``. La traducción a tablas de
precios normalizadas es un paso posterior y separado.

Si ocurre un error de base de datos, la excepción se propaga y el lote queda
en estado ``running``: señal de una importación interrumpida.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import DataSource, ImportBatch, ImportIssue, RawRecord


class SourceNotFoundError(LookupError):
    """La fuente indicada no existe en ``data_source``."""


class InvalidRecordError(ValueError):
    """El registro no se puede guardar como original."""


@dataclass(frozen=True)
class ImportResult:
    batch_id: int
    status: str
    rows_received: int
    rows_loaded: int
    rows_duplicate: int
    errors: int


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Serialización determinística: mismo contenido, mismo texto.

    El orden de las claves no influye. Rechaza NaN e infinitos, que no son
    JSON válido.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def payload_hash(payload: Mapping[str, Any]) -> str:
    """SHA-256 (hex) del contenido canónico de un registro."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _hash_or_raise(record: object) -> str:
    if not isinstance(record, Mapping):
        raise InvalidRecordError(
            f"se esperaba un diccionario y llegó {type(record).__name__}"
        )
    try:
        return payload_hash(record)
    except (TypeError, ValueError) as exc:
        raise InvalidRecordError(f"no serializable como JSON: {exc}") from exc


def _final_status(errors: int, accepted: int) -> str:
    if errors == 0:
        return "succeeded"
    return "partial" if accepted > 0 else "failed"


def run_import(
    session: Session,
    source_code: str,
    records: Iterable[Mapping[str, Any]],
    *,
    parameters: dict[str, Any] | None = None,
    normalization_version: str | None = None,
) -> ImportResult:
    """Importa ``records`` de la fuente ``source_code`` en un lote nuevo.

    Si la fuente falla mientras entrega registros, se conserva lo ya cargado,
    el lote queda como ``partial`` o ``failed`` y la excepción original se
    vuelve a lanzar.
    """
    source = session.scalar(select(DataSource).where(DataSource.code == source_code))
    if source is None:
        raise SourceNotFoundError(f"La fuente '{source_code}' no existe")
    source_id = source.id

    batch = ImportBatch(
        source_id=source_id,
        parameters=parameters,
        normalization_version=normalization_version,
    )
    session.add(batch)
    session.commit()  # el lote queda registrado como 'running'
    batch_id = batch.id

    received = loaded = duplicates = errors = 0
    source_failure: Exception | None = None

    iterator = iter(records)
    while True:
        try:
            record = next(iterator)
        except StopIteration:
            break
        except Exception as exc:  # noqa: BLE001 - se re-lanza al final del lote
            source_failure = exc
            break

        received += 1
        try:
            digest = _hash_or_raise(record)
        except InvalidRecordError as exc:
            errors += 1
            session.add(
                ImportIssue(batch_id=batch_id, message=f"Registro #{received}: {exc}")
            )
            continue

        stmt = (
            pg_insert(RawRecord)
            .values(
                batch_id=batch_id,
                source_id=source_id,
                payload=dict(record),
                payload_hash=digest,
            )
            .on_conflict_do_nothing(constraint="uq_raw_record_source_hash")
            .returning(RawRecord.id)
        )
        if session.execute(stmt).scalar_one_or_none() is None:
            duplicates += 1
        else:
            loaded += 1

    if source_failure is not None:
        errors += 1
        # Solo el tipo de error: el mensaje podría incluir URLs o credenciales.
        # El detalle completo viaja en la excepción que se re-lanza.
        session.add(
            ImportIssue(
                batch_id=batch_id,
                message=(
                    "La fuente falló al entregar registros: "
                    f"{type(source_failure).__name__}"
                ),
            )
        )

    status = _final_status(errors, loaded + duplicates)
    session.execute(
        update(ImportBatch)
        .where(ImportBatch.id == batch_id)
        .values(
            finished_at=func.now(),
            status=status,
            rows_received=received,
            rows_loaded=loaded,
        )
    )
    session.commit()

    if source_failure is not None:
        raise source_failure

    return ImportResult(
        batch_id=batch_id,
        status=status,
        rows_received=received,
        rows_loaded=loaded,
        rows_duplicate=duplicates,
        errors=errors,
    )
