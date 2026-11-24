"""Tests de las reglas de vencimiento.

Los feriados de estos tests son INVENTADOS: sirven para probar la regla, no
representan ningún calendario oficial. Las fechas esperadas se calcularon a
mano sobre el calendario de 2026 (1/1/2026 fue jueves; 15/11/2026, domingo).
"""

from datetime import date

import pytest

from app.instruments import (
    A3_SOJA_CHICAGO,
    A3_SOJA_MINI,
    A3_SOJA_USD,
    CBOT_ZS,
    estimate_last_trading_day,
)
from app.instruments.expiry import (
    business_day_before_15th,
    is_business_day,
    last_business_day_of_previous_month,
    session_before_last_five,
)

# ---------- días hábiles ----------


def test_is_business_day():
    assert is_business_day(date(2026, 11, 13))  # viernes
    assert not is_business_day(date(2026, 11, 14))  # sábado
    assert not is_business_day(date(2026, 11, 15))  # domingo
    assert not is_business_day(date(2026, 11, 13), holidays={date(2026, 11, 13)})


# ---------- CBOT: día hábil anterior al 15 ----------


def test_cbot_cuando_el_15_cae_domingo_vence_el_viernes_13():
    assert business_day_before_15th(2026, 11) == date(2026, 11, 13)


def test_cbot_si_el_dia_13_es_feriado_vence_el_jueves_12():
    assert business_day_before_15th(2026, 11, {date(2026, 11, 13)}) == date(2026, 11, 12)


def test_cbot_cuando_el_14_es_dia_habil_vence_el_14():
    # 15/1/2026 es jueves, así que el día hábil anterior es el miércoles 14.
    assert business_day_before_15th(2026, 1) == date(2026, 1, 14)


# ---------- A3 con entrega: rueda previa a las últimas cinco ----------


def test_a3_rueda_previa_a_las_ultimas_cinco_sin_feriados():
    # Últimas cinco ruedas de nov-2026: 24, 25, 26, 27 y 30 -> vence el lunes 23.
    assert session_before_last_five(2026, 11) == date(2026, 11, 23)


def test_a3_un_feriado_corre_la_fecha():
    # Con el 27 feriado, las últimas cinco son 23, 24, 25, 26 y 30 -> vence el 20.
    assert session_before_last_five(2026, 11, {date(2026, 11, 27)}) == date(2026, 11, 20)


# ---------- A3 Mini: último día hábil del mes anterior ----------


def test_mini_contrato_de_diciembre_vence_el_ultimo_habil_de_noviembre():
    assert last_business_day_of_previous_month(2026, 12) == date(2026, 11, 30)


def test_mini_cruza_el_cambio_de_anio():
    assert last_business_day_of_previous_month(2027, 1) == date(2026, 12, 31)
    assert last_business_day_of_previous_month(2027, 1, {date(2026, 12, 31)}) == date(
        2026, 12, 30
    )


def test_mini_si_el_ultimo_dia_cae_fin_de_semana_retrocede_al_viernes():
    # 31/1/2026 es sábado.
    assert last_business_day_of_previous_month(2026, 2) == date(2026, 1, 30)


# ---------- despacho por contrato ----------


def test_estimate_usa_la_regla_de_cada_contrato():
    assert estimate_last_trading_day(CBOT_ZS, 2026, 11) == date(2026, 11, 13)
    assert estimate_last_trading_day(A3_SOJA_USD, 2026, 11) == date(2026, 11, 23)
    assert estimate_last_trading_day(A3_SOJA_MINI, 2026, 12) == date(2026, 11, 30)


def test_estimate_rechaza_un_mes_que_el_contrato_no_lista():
    with pytest.raises(ValueError):
        estimate_last_trading_day(CBOT_ZS, 2026, 6)  # CBOT soja no lista junio


def test_estimate_no_calcula_la_regla_de_soja_chicago():
    with pytest.raises(NotImplementedError):
        estimate_last_trading_day(A3_SOJA_CHICAGO, 2026, 11)


@pytest.mark.parametrize("mes", [0, 13, -1])
def test_mes_invalido(mes):
    with pytest.raises(ValueError):
        business_day_before_15th(2026, mes)
    with pytest.raises(ValueError):
        estimate_last_trading_day(A3_SOJA_USD, 2026, mes)
