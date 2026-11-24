"""Tests del importador genérico.

Todos los datos son DATOS DE PRUEBA inventados para los tests; no son datos
de mercado.
"""

import math

import pytest
from sqlalchemy import func, select

from app.ingestion import SourceNotFoundError, payload_hash, run_import
from app.models import DataSource, ImportBatch, ImportIssue, RawRecord

# ---------- hash (sin base de datos) ----------


def test_hash_no_depende_del_orden_de_las_claves():
    assert payload_hash({"a": 1, "b": 2}) == payload_hash({"b": 2, "a": 1})


def test_hash_cambia_si_cambia_el_contenido():
    assert payload_hash({"a": 1}) != payload_hash({"a": 2})


def test_hash_rechaza_nan():
    with pytest.raises(ValueError):
        payload_hash({"a": math.nan})


def test_hash_rechaza_tipos_no_serializables():
    with pytest.raises(TypeError):
        payload_hash({"a": {1, 2}})


# ---------- importador (contra PostgreSQL, con rollback) ----------


@pytest.fixture
def fuente(db_session):
    src = DataSource(code="test_fuente_a", name="Fuente de prueba A")
    db_session.add(src)
    db_session.commit()
    return src


def _contar_raw(session, batch_id):
    return session.scalar(
        select(func.count()).select_from(RawRecord).where(RawRecord.batch_id == batch_id)
    )


def test_importa_registros_nuevos(db_session, fuente):
    registros = [{"dato": "prueba", "n": 1}, {"dato": "prueba", "n": 2}]

    r = run_import(db_session, "test_fuente_a", registros)

    assert (r.rows_received, r.rows_loaded, r.rows_duplicate, r.errors) == (2, 2, 0, 0)
    assert r.status == "succeeded"
    assert _contar_raw(db_session, r.batch_id) == 2
    lote = db_session.get(ImportBatch, r.batch_id)
    assert lote.status == "succeeded"
    assert lote.finished_at is not None
    assert (lote.rows_received, lote.rows_loaded) == (2, 2)


def test_preserva_el_original_sin_modificar(db_session, fuente):
    original = {"z": 1, "a": {"x": [1, 2, 3]}, "texto": "ñandú"}

    r = run_import(db_session, "test_fuente_a", [original])

    guardado = db_session.scalar(
        select(RawRecord).where(RawRecord.batch_id == r.batch_id)
    )
    assert guardado.payload == original
    assert guardado.payload_hash == payload_hash(original)


def test_reimportar_lo_mismo_no_duplica(db_session, fuente):
    registros = [{"n": 1}, {"n": 2}]
    run_import(db_session, "test_fuente_a", registros)

    r2 = run_import(db_session, "test_fuente_a", registros)

    assert (r2.rows_loaded, r2.rows_duplicate) == (0, 2)
    assert r2.status == "succeeded"
    total = db_session.scalar(
        select(func.count())
        .select_from(RawRecord)
        .where(RawRecord.source_id == fuente.id)
    )
    assert total == 2


def test_duplicados_dentro_del_mismo_lote(db_session, fuente):
    r = run_import(db_session, "test_fuente_a", [{"n": 1}, {"n": 1}, {"n": 2}])

    assert (r.rows_received, r.rows_loaded, r.rows_duplicate) == (3, 2, 1)


def test_el_mismo_contenido_en_dos_fuentes_se_guarda_en_ambas(db_session, fuente):
    db_session.add(DataSource(code="test_fuente_b", name="Fuente de prueba B"))
    db_session.commit()

    ra = run_import(db_session, "test_fuente_a", [{"n": 1}])
    rb = run_import(db_session, "test_fuente_b", [{"n": 1}])

    assert ra.rows_loaded == 1
    assert rb.rows_loaded == 1


def test_registro_invalido_se_registra_y_el_resto_se_carga(db_session, fuente):
    registros = [{"n": 1}, "no soy un diccionario", {"n": math.nan}, {"n": 2}]

    r = run_import(db_session, "test_fuente_a", registros)

    assert (r.rows_received, r.rows_loaded, r.errors) == (4, 2, 2)
    assert r.status == "partial"
    problemas = db_session.scalars(
        select(ImportIssue).where(ImportIssue.batch_id == r.batch_id)
    ).all()
    assert len(problemas) == 2
    assert any("#2" in p.message for p in problemas)
    assert any("#3" in p.message for p in problemas)


def test_si_todo_es_invalido_el_lote_falla(db_session, fuente):
    r = run_import(db_session, "test_fuente_a", ["x", 5])

    assert r.status == "failed"
    assert r.rows_loaded == 0
    assert r.errors == 2


def test_fuente_inexistente_no_crea_lote(db_session):
    antes = db_session.scalar(select(func.count()).select_from(ImportBatch))

    with pytest.raises(SourceNotFoundError):
        run_import(db_session, "no_existe", [{"n": 1}])

    despues = db_session.scalar(select(func.count()).select_from(ImportBatch))
    assert despues == antes


def test_si_la_fuente_falla_a_mitad_se_conserva_lo_cargado(db_session, fuente):
    class CaidaDeRed(Exception):
        pass

    def fuente_que_se_cae():
        yield {"n": 1}
        yield {"n": 2}
        raise CaidaDeRed("http://ejemplo/?api_key=SECRETO")

    with pytest.raises(CaidaDeRed):
        run_import(db_session, "test_fuente_a", fuente_que_se_cae())

    lote = db_session.scalar(select(ImportBatch).order_by(ImportBatch.id.desc()))
    assert lote.status == "partial"
    assert (lote.rows_received, lote.rows_loaded) == (2, 2)
    assert _contar_raw(db_session, lote.id) == 2
    problema = db_session.scalar(
        select(ImportIssue).where(ImportIssue.batch_id == lote.id)
    )
    assert "CaidaDeRed" in problema.message
    # El mensaje de la excepción (puede traer credenciales) no se guarda.
    assert "SECRETO" not in problema.message


def test_guarda_parametros_y_version_de_normalizacion(db_session, fuente):
    r = run_import(
        db_session,
        "test_fuente_a",
        [{"n": 1}],
        parameters={"desde": "2026-01-01", "hasta": "2026-01-07"},
        normalization_version="v0",
    )

    lote = db_session.get(ImportBatch, r.batch_id)
    assert lote.parameters == {"desde": "2026-01-01", "hasta": "2026-01-07"}
    assert lote.normalization_version == "v0"
