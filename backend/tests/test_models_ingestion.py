from app.db.base import Base
import app.models  # noqa: F401  (registra los modelos)


def test_tablas_de_ingesta_registradas():
    tablas = set(Base.metadata.tables)

    assert {"data_source", "import_batch", "raw_record", "import_error"} <= tablas


def test_raw_record_evita_duplicados_por_fuente_y_hash():
    tabla = Base.metadata.tables["raw_record"]
    unicas = {
        tuple(c.name for c in constraint.columns)
        for constraint in tabla.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }

    assert ("source_id", "payload_hash") in unicas


def test_import_batch_restringe_los_estados_validos():
    tabla = Base.metadata.tables["import_batch"]
    nombres = {c.name for c in tabla.constraints}

    assert "ck_import_batch_status" in nombres


def test_el_payload_original_es_obligatorio():
    tabla = Base.metadata.tables["raw_record"]

    assert tabla.c.payload.nullable is False
    assert tabla.c.payload_hash.nullable is False
