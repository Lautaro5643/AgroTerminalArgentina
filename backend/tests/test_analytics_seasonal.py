"""Tests del comparador estacional.

Todos los datos son INVENTADOS (``DataKind.TEST``). Los resultados esperados se
calcularon a mano; no representan ningún mercado.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.analytics import (
    DataKind,
    MissingReason,
    NoCurrentObservationError,
    Series,
    SeriesError,
    compare_to_history,
)
from app.instruments import PriceType


def make(pairs, **kw):
    params = dict(
        name="serie de prueba",
        unit="USD/t",
        data_kind=DataKind.TEST,
        source="inventado para tests",
        price_type=PriceType.UNSPECIFIED,
    )
    params.update(kw)
    return Series.from_pairs(pairs=pairs, **params)


BASE = [
    (date(2022, 11, 25), 100),
    (date(2023, 11, 25), 200),
    (date(2024, 11, 25), 300),
    (date(2025, 11, 25), 400),
    (date(2026, 11, 25), 350),
]


def test_estadisticas_calculadas_a_mano():
    r = compare_to_history(make(BASE), date(2026, 11, 25), years_back=4)
    assert r.current_value == Decimal(350)
    assert [y.year for y in r.years] == [2022, 2023, 2024, 2025]
    s = r.stats
    assert (s.count, s.mean, s.median, s.minimum, s.maximum) == (
        4,
        Decimal(250),
        Decimal(250),
        Decimal(100),
        Decimal(400),
    )
    # desvío muestral: raíz de 50000/3
    assert abs(s.stdev - Decimal("129.0994449")) < Decimal("0.0000001")
    assert r.diff_vs_mean == Decimal(100)
    assert r.pct_diff_vs_mean == Decimal(40)
    assert abs(r.z_score - Decimal("0.7745966692")) < Decimal("0.0000001")
    assert r.percentile_rank == Decimal(75)  # 3 de 4 valores previos son menores


def test_el_ano_corriente_no_entra_en_las_estadisticas():
    r = compare_to_history(make(BASE), date(2026, 11, 25), years_back=10)
    assert 2026 not in [y.year for y in r.years]
    assert r.stats.count == 4  # solo 2022..2025 tienen dato


def test_anos_sin_dato_quedan_como_faltantes_con_motivo():
    r = compare_to_history(make(BASE), date(2026, 11, 25), years_back=6)
    faltan = {y.year: y.missing_reason for y in r.years if y.value is None}
    assert faltan == {
        2020: MissingReason.NO_OBSERVATION,
        2021: MissingReason.NO_OBSERVATION,
    }
    assert r.stats.count == 4


def test_percentil_midrank_con_empates():
    pairs = [(date(2024, 5, 10), 10), (date(2025, 5, 10), 20), (date(2026, 5, 10), 20)]
    r = compare_to_history(make(pairs), date(2026, 5, 10), years_back=2)
    # previos: 10 y 20; actual 20 -> 1 menor + 0,5 igual = 1,5 de 2 = 75
    assert r.percentile_rank == Decimal(75)


def test_un_solo_ano_no_tiene_desvio():
    pairs = [(date(2025, 5, 10), 20), (date(2026, 5, 10), 30)]
    r = compare_to_history(make(pairs), date(2026, 5, 10), years_back=1)
    assert r.stats.count == 1
    assert r.stats.stdev is None
    assert r.z_score is None
    assert r.percentile_rank == Decimal(100)


def test_valores_previos_iguales_no_dan_z_score():
    pairs = [(date(2024, 5, 10), 20), (date(2025, 5, 10), 20), (date(2026, 5, 10), 30)]
    r = compare_to_history(make(pairs), date(2026, 5, 10), years_back=2)
    assert r.stats.stdev == Decimal(0)
    assert r.z_score is None


def test_promedio_cero_no_da_porcentaje():
    pairs = [(date(2024, 5, 10), -5), (date(2025, 5, 10), 5), (date(2026, 5, 10), 3)]
    r = compare_to_history(make(pairs), date(2026, 5, 10), years_back=2)
    assert r.stats.mean == 0
    assert r.pct_diff_vs_mean is None


def test_ningun_ano_con_dato_deja_stats_vacias():
    r = compare_to_history(make([(date(2026, 5, 10), 3)]), date(2026, 5, 10), years_back=3)
    assert r.stats is None
    assert r.diff_vs_mean is None and r.percentile_rank is None


# ---------- tolerancia y fechas ----------


def test_sin_tolerancia_se_exige_la_fecha_exacta():
    # 25/11/2023 fue sábado: la serie tiene el viernes 24.
    pairs = [(date(2023, 11, 24), 200), (date(2026, 11, 25), 350)]
    r = compare_to_history(make(pairs), date(2026, 11, 25), years_back=3)
    y2023 = next(y for y in r.years if y.year == 2023)
    assert y2023.value is None
    assert y2023.missing_reason is MissingReason.NO_OBSERVATION


def test_con_tolerancia_usa_el_dato_anterior_e_informa_la_fecha_real():
    pairs = [(date(2023, 11, 24), 200), (date(2026, 11, 25), 350)]
    r = compare_to_history(make(pairs), date(2026, 11, 25), years_back=3, tolerance_days=2)
    y2023 = next(y for y in r.years if y.year == 2023)
    assert y2023.value == Decimal(200)
    assert y2023.observation_date == date(2023, 11, 24)
    assert y2023.lag_days == 1


def test_nunca_usa_un_dato_posterior_a_la_fecha_pedida():
    pairs = [(date(2023, 11, 27), 999), (date(2026, 11, 25), 350)]
    r = compare_to_history(make(pairs), date(2026, 11, 25), years_back=3, tolerance_days=5)
    y2023 = next(y for y in r.years if y.year == 2023)
    assert y2023.value is None


def test_la_tolerancia_tiene_limite():
    pairs = [(date(2023, 11, 20), 200), (date(2026, 11, 25), 350)]
    r = compare_to_history(make(pairs), date(2026, 11, 25), years_back=3, tolerance_days=2)
    assert next(y for y in r.years if y.year == 2023).value is None


def test_29_de_febrero_no_se_reemplaza_por_el_28():
    pairs = [
        (date(2024, 2, 29), 10),
        (date(2025, 2, 28), 99),
        (date(2028, 2, 29), 20),
    ]
    r = compare_to_history(make(pairs), date(2028, 2, 29), years_back=4)
    por_ano = {y.year: y for y in r.years}
    assert por_ano[2024].value == Decimal(10)
    for ano in (2025, 2026, 2027):
        assert por_ano[ano].missing_reason is MissingReason.NO_SUCH_DATE
        assert por_ano[ano].target_date is None
        assert por_ano[ano].lag_days is None
    assert r.stats.count == 1


def test_sin_dato_actual_falla_en_vez_de_inventar():
    with pytest.raises(NoCurrentObservationError):
        compare_to_history(make(BASE[:4]), date(2026, 11, 25), years_back=3)


def test_dato_actual_con_tolerancia_informa_su_fecha():
    pairs = BASE[:4] + [(date(2026, 11, 24), 350)]
    r = compare_to_history(make(pairs), date(2026, 11, 25), years_back=3, tolerance_days=1)
    assert r.current_date == date(2026, 11, 24)
    assert r.as_of == date(2026, 11, 25)


def test_el_resultado_conserva_el_origen_y_el_tipo_de_dato():
    r = compare_to_history(make(BASE), date(2026, 11, 25), years_back=2)
    assert r.data_kind is DataKind.TEST
    assert r.source == "inventado para tests"
    assert r.unit == "USD/t"


@pytest.mark.parametrize("kw", [{"years_back": 0}, {"years_back": 2, "tolerance_days": -1}])
def test_parametros_invalidos(kw):
    with pytest.raises(ValueError):
        compare_to_history(make(BASE), date(2026, 11, 25), **kw)


# ---------- construcción de series ----------


def test_series_rechaza_float():
    with pytest.raises(TypeError):
        make([(date(2026, 1, 1), 1.5)])


def test_series_rechaza_fechas_repetidas_y_datetime():
    with pytest.raises(SeriesError):
        make([(date(2026, 1, 1), 1), (date(2026, 1, 1), 2)])
    from datetime import datetime

    with pytest.raises(TypeError):
        make([(datetime(2026, 1, 1), 1)])


def test_series_se_ordena_por_fecha():
    s = make([(date(2026, 1, 3), 3), (date(2026, 1, 1), 1)])
    assert [d for d, _ in s.observations] == [date(2026, 1, 1), date(2026, 1, 3)]
