from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.instruments import (
    A3_SOJA_CHICAGO,
    A3_SOJA_MINI,
    A3_SOJA_USD,
    CBOT_ZS,
    SOYBEAN_CONTRACTS,
    ExpiryRule,
    PriceUnit,
    Settlement,
    SizeUnit,
    get_contract,
)
from app.instruments.contracts import CBOT_ZS_MONTH_CODES

D = Decimal


def test_cada_contrato_cita_su_fuente():
    for spec in SOYBEAN_CONTRACTS.values():
        assert spec.source_url.startswith("https://"), spec.key
        assert spec.source_note.strip(), spec.key


def test_los_contratos_con_datos_sin_confirmar_lo_declaran():
    # Todo lo que la fuente no dice debe quedar como None o figurar en caveats.
    for spec in (A3_SOJA_USD, A3_SOJA_MINI, A3_SOJA_CHICAGO):
        assert spec.tick is None, spec.key
        assert spec.caveats, spec.key


def test_cbot_zs_segun_cme():
    assert CBOT_ZS.size == D(5000)
    assert CBOT_ZS.size_unit is SizeUnit.BUSHEL
    assert CBOT_ZS.price_unit is PriceUnit.USC_PER_BUSHEL
    assert CBOT_ZS.tick == D("0.25")
    assert CBOT_ZS.settlement is Settlement.PHYSICAL
    assert CBOT_ZS.expiry_rule is ExpiryRule.BUSINESS_DAY_BEFORE_15TH
    assert CBOT_ZS.months == (1, 3, 5, 7, 8, 9, 11)


def test_las_letras_de_mes_cbot_coinciden_con_los_meses_listados():
    assert tuple(sorted(CBOT_ZS_MONTH_CODES)) == CBOT_ZS.months
    assert "".join(CBOT_ZS_MONTH_CODES[m] for m in CBOT_ZS.months) == "FHKNQUX"


def test_tamanos_de_los_contratos_a3_segun_su_guia():
    assert (A3_SOJA_USD.size, A3_SOJA_USD.size_unit) == (D(100), SizeUnit.TONNE)
    assert (A3_SOJA_MINI.size, A3_SOJA_MINI.size_unit) == (D(10), SizeUnit.TONNE)
    assert (A3_SOJA_CHICAGO.size, A3_SOJA_CHICAGO.size_unit) == (D(5), SizeUnit.TONNE)


def test_liquidacion_de_los_contratos_a3():
    assert A3_SOJA_USD.settlement is Settlement.PHYSICAL
    assert A3_SOJA_MINI.settlement is Settlement.CASH
    assert A3_SOJA_CHICAGO.settlement is Settlement.CASH


def test_size_in_tonnes_hace_explicita_la_diferencia_de_tamano():
    # Un contrato CBOT (~136 t) no es comparable "uno a uno" con uno de A3.
    assert CBOT_ZS.size_in_tonnes().quantize(D("1")) == D("136")
    assert A3_SOJA_USD.size_in_tonnes() == D(100)
    assert A3_SOJA_CHICAGO.size_in_tonnes() == D(5)


def test_get_contract():
    assert get_contract("CBOT_ZS") is CBOT_ZS
    with pytest.raises(KeyError):
        get_contract("NO_EXISTE")


def test_las_especificaciones_son_inmutables():
    with pytest.raises(FrozenInstanceError):
        CBOT_ZS.size = D(1)
