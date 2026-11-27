"""Tests de relaciones entre series. Datos INVENTADOS (``DataKind.TEST``)."""

from datetime import date
from decimal import Decimal

import pytest

from app.analytics import (
    DataKind,
    DataKindMismatchError,
    PriceTypeMismatchError,
    Series,
    compare_to_history,
    ratio,
    spread,
)
from app.instruments import PriceType, UnitMismatchError

D1, D2, D3 = date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)


def make(name, pairs, *, unit="USD/t", kind=DataKind.TEST, ptype=PriceType.SETTLEMENT):
    return Series.from_pairs(
        name=name, unit=unit, data_kind=kind, source=f"inventado:{name}",
        price_type=ptype, pairs=pairs,
    )


def test_razon_soja_sobre_maiz_a_mano():
    soja = make("soja", [(D1, 400), (D2, 440)])
    maiz = make("maiz", [(D1, 200), (D2, 220)])
    r = ratio(soja, maiz, name="soja/maiz")
    assert r.series.as_dict() == {D1: Decimal(2), D2: Decimal(2)}
    assert r.series.unit == "ratio"
    assert r.series.data_kind is DataKind.TEST
    assert "soja" in r.series.source and "maiz" in r.series.source


def test_razon_con_unidades_distintas_da_unidad_derivada_sin_convertir():
    a = make("a", [(D1, 300)], unit="USD/t")
    b = make("b", [(D1, 600)], unit="USc/bu")
    r = ratio(a, b, name="a/b")
    assert r.series.unit == "USD/t/USc/bu"
    assert r.series.as_dict() == {D1: Decimal("0.5")}


def test_diferencia_entre_dos_meses():
    mar = make("mar", [(D1, 410), (D2, 415)])
    may = make("may", [(D1, 400), (D2, 420)])
    r = spread(mar, may, name="mar - may")
    assert r.series.as_dict() == {D1: Decimal(10), D2: Decimal(-5)}
    assert r.series.price_type is PriceType.SETTLEMENT


def test_diferencia_exige_misma_unidad():
    a = make("a", [(D1, 1)], unit="USD/t")
    b = make("b", [(D1, 1)], unit="USc/bu")
    with pytest.raises(UnitMismatchError):
        spread(a, b, name="x")


def test_no_se_mezclan_datos_de_distinto_tipo():
    real = make("a", [(D1, 1)], kind=DataKind.REAL)
    prueba = make("b", [(D1, 1)], kind=DataKind.TEST)
    with pytest.raises(DataKindMismatchError):
        spread(real, prueba, name="x")
    with pytest.raises(DataKindMismatchError):
        ratio(real, prueba, name="x")


def test_no_se_mezclan_tipos_de_precio_salvo_pedido_explicito():
    ajuste = make("fisico", [(D1, 10)], ptype=PriceType.SETTLEMENT)
    ultimo = make("futuro", [(D1, 7)], ptype=PriceType.LAST)
    with pytest.raises(PriceTypeMismatchError):
        spread(ajuste, ultimo, name="x")
    r = spread(ajuste, ultimo, name="x", allow_mixed_price_types=True)
    assert r.series.as_dict() == {D1: Decimal(3)}
    assert r.series.price_type is PriceType.UNSPECIFIED


def test_las_fechas_no_comunes_se_informan_y_no_se_rellenan():
    a = make("a", [(D1, 10), (D2, 20)])
    b = make("b", [(D2, 5), (D3, 6)])
    r = spread(a, b, name="x")
    assert r.series.as_dict() == {D2: Decimal(15)}
    assert r.only_in_first == (D1,)
    assert r.only_in_second == (D3,)


def test_denominador_cero_se_omite_y_se_informa():
    a = make("a", [(D1, 10), (D2, 20)])
    b = make("b", [(D1, 0), (D2, 5)])
    r = ratio(a, b, name="x")
    assert r.series.as_dict() == {D2: Decimal(4)}
    assert r.skipped_zero_denominator == (D1,)


def test_la_relacion_se_puede_comparar_contra_su_historia():
    # razón soja/maíz constante en 2: el 2026 es 2,5 -> por encima de todo lo previo
    soja = make("soja", [(date(2024, 3, 1), 400), (date(2025, 3, 1), 420), (date(2026, 3, 1), 500)])
    maiz = make("maiz", [(date(2024, 3, 1), 200), (date(2025, 3, 1), 210), (date(2026, 3, 1), 200)])
    rel = ratio(soja, maiz, name="soja/maiz").series
    c = compare_to_history(rel, date(2026, 3, 1), years_back=2)
    assert c.current_value == Decimal("2.5")
    assert c.stats.mean == Decimal(2)
    assert c.percentile_rank == Decimal(100)
    assert c.data_kind is DataKind.TEST  # el origen de prueba se arrastra
