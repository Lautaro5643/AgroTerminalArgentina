"""Tests de unidades y conversiones.

Los valores esperados salen de las fuentes citadas en app/instruments/units.py
(tabla del U.S. Grains Council y el equivalente de ~136 t que informa CME).
"""

from decimal import Decimal

import pytest

from app.instruments.units import as_decimal

from app.instruments import (
    Commodity,
    Price,
    PriceUnit,
    UnitMismatchError,
    bushels_to_tonnes,
    tonnes_to_bushels,
    usc_per_bushel_to_usd_per_tonne,
    usd_per_tonne_to_usc_per_bushel,
)
from app.instruments.units import bushels_per_tonne, tonnes_per_bushel

D = Decimal


def test_tonnes_per_bushel_de_la_soja_coincide_con_la_tabla_de_referencia():
    assert tonnes_per_bushel(Commodity.SOYBEAN).quantize(D("0.0000001")) == D("0.0272155")


def test_bushels_per_tonne_de_soja_y_trigo_coinciden_con_la_tabla():
    assert bushels_per_tonne(Commodity.SOYBEAN).quantize(D("0.0001")) == D("36.7437")
    assert bushels_per_tonne(Commodity.WHEAT).quantize(D("0.0001")) == D("36.7437")


def test_bushels_per_tonne_del_maiz_coincide_con_la_tabla():
    assert bushels_per_tonne(Commodity.CORN).quantize(D("0.001")) == D("39.368")


def test_el_contrato_cbot_de_soja_equivale_a_unas_136_toneladas():
    # CME: 5.000 bushels = "aprox. 136 toneladas métricas".
    assert bushels_to_tonnes(Commodity.SOYBEAN, 5000).quantize(D("1")) == D("136")


@pytest.mark.parametrize("commodity", list(Commodity))
def test_ida_y_vuelta_bushels_toneladas(commodity):
    tonnes = bushels_to_tonnes(commodity, 12345)

    assert tonnes_to_bushels(commodity, tonnes).quantize(D("0.000001")) == D("12345")


def test_conversion_de_precio_centavos_por_bushel_a_dolares_por_tonelada():
    precio = Price(D("1000"), PriceUnit.USC_PER_BUSHEL)  # US$10 por bushel

    convertido = usc_per_bushel_to_usd_per_tonne(Commodity.SOYBEAN, precio)

    assert convertido.unit is PriceUnit.USD_PER_TONNE
    assert convertido.value.quantize(D("0.01")) == D("367.44")  # 10 x 36,7437


def test_conversion_de_precio_dolares_por_tonelada_a_centavos_por_bushel():
    precio = Price(D("367.437104"), PriceUnit.USD_PER_TONNE)

    convertido = usd_per_tonne_to_usc_per_bushel(Commodity.SOYBEAN, precio)

    assert convertido.unit is PriceUnit.USC_PER_BUSHEL
    assert convertido.value.quantize(D("0.01")) == D("1000.00")


def test_ida_y_vuelta_de_precio():
    original = Price(D("1234.5"), PriceUnit.USC_PER_BUSHEL)

    de_ida = usc_per_bushel_to_usd_per_tonne(Commodity.CORN, original)
    de_vuelta = usd_per_tonne_to_usc_per_bushel(Commodity.CORN, de_ida)

    assert de_vuelta.value.quantize(D("0.000001")) == D("1234.5")
    assert de_vuelta.unit is PriceUnit.USC_PER_BUSHEL


def test_acepta_precios_negativos_como_los_de_un_spread():
    spread = Price(D("-25"), PriceUnit.USC_PER_BUSHEL)

    convertido = usc_per_bushel_to_usd_per_tonne(Commodity.SOYBEAN, spread)

    assert convertido.value < 0


def test_rechaza_convertir_un_precio_en_la_unidad_equivocada():
    en_dolares_por_tonelada = Price(D("350"), PriceUnit.USD_PER_TONNE)
    en_centavos = Price(D("1000"), PriceUnit.USC_PER_BUSHEL)

    with pytest.raises(UnitMismatchError):
        usc_per_bushel_to_usd_per_tonne(Commodity.SOYBEAN, en_dolares_por_tonelada)
    with pytest.raises(UnitMismatchError):
        usd_per_tonne_to_usc_per_bushel(Commodity.SOYBEAN, en_centavos)


def test_rechaza_float_porque_es_impreciso():
    with pytest.raises(TypeError):
        bushels_to_tonnes(Commodity.SOYBEAN, 1.5)
    with pytest.raises(TypeError):
        tonnes_to_bushels(Commodity.SOYBEAN, 0.1)
    with pytest.raises(TypeError):
        Price(1.5, PriceUnit.USD_PER_TONNE)


def test_rechaza_bool_y_texto():
    with pytest.raises(TypeError):
        bushels_to_tonnes(Commodity.SOYBEAN, True)
    with pytest.raises(TypeError):
        bushels_to_tonnes(Commodity.SOYBEAN, "100")


def test_el_precio_es_inmutable():
    precio = Price(D("1"), PriceUnit.USD_PER_TONNE)

    with pytest.raises(Exception):
        precio.value = D("2")


@pytest.mark.parametrize("valor", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_as_decimal_rechaza_no_finitos(valor):
    with pytest.raises(ValueError):
        as_decimal(valor)
