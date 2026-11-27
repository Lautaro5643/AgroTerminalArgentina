"""Tests de la calculadora de pase. Números INVENTADOS, resultados calculados a mano.

Caso base: 1/1/2026 -> 15/3/2026 son 73 días, o sea 73/365 = 0,2 de año exacto.
Cercano 400, lejano 412 USD/t: pase 12 = 3 % = 15 % anualizado.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.calculators import (
    CarryInputError,
    PriceTypeMismatchError,
    WarrantTerms,
    calculate_carry,
)
from app.instruments import Price, PriceType, PriceUnit, UnitMismatchError
from app.main import app

NEAR_D, FAR_D = date(2026, 1, 1), date(2026, 3, 15)


def usd(v):
    return Price(Decimal(v), PriceUnit.USD_PER_TONNE)


def base(**kw):
    params = dict(
        near=usd(400), far=usd(412), near_date=NEAR_D, far_date=FAR_D,
        price_type=PriceType.SETTLEMENT, storage_cost_annual_pct=Decimal(10),
    )
    params.update(kw)
    return calculate_carry(**params)


def test_pase_y_neto_a_mano():
    r = base()
    assert r.days == 73
    assert r.pase == usd(12)
    assert r.pase_pct == Decimal(3)
    assert r.pase_annualized_pct == Decimal(15)
    assert r.carry_cost == usd(8)  # 400 * 10 % * 0,2
    assert r.net == usd(4)
    assert r.net_annual_pct == Decimal(5)  # 15 - 10
    assert r.total_annual_costs_pct == Decimal(10)
    assert r.price_type is PriceType.SETTLEMENT


def test_otros_costos_anuales_se_suman():
    r = base(other_annual_costs_pct={"financiación": Decimal(2)})
    assert r.cost_breakdown["financiación"] == usd("1.6")
    assert r.net == usd("2.4")
    assert r.net_annual_pct == Decimal(3)  # 15 - 10 - 2


def test_costos_fijos_se_restan_en_el_neto():
    r = base(fixed_costs={"comisión": Decimal("0.5")})
    assert r.fixed_costs_total == usd("0.5")
    assert r.net == usd("3.5")
    assert r.net_annual_pct == Decimal("4.375")  # 3,5 / 400 * 5 * 100


def test_pase_negativo():
    r = base(far=usd(396))
    assert r.pase == usd(-4)
    assert r.pase_pct == Decimal(-1)
    assert r.pase_annualized_pct == Decimal(-5)
    assert r.net == usd(-12)


def test_la_base_de_dias_es_un_parametro():
    r = base(day_count_basis=360)
    assert r.day_count_basis == 360
    assert r.pase_annualized_pct == Decimal(3) * 360 / 73


def test_costo_cero_el_neto_es_el_pase():
    r = base(storage_cost_annual_pct=0)
    assert r.net == r.pase


def test_precios_en_unidades_distintas_fallan_sin_convertir():
    with pytest.raises(UnitMismatchError):
        base(far=Price(Decimal(412), PriceUnit.USC_PER_BUSHEL))


def test_tipos_de_precio_distintos_fallan():
    with pytest.raises(PriceTypeMismatchError):
        base(far_price_type=PriceType.LAST)


@pytest.mark.parametrize(
    "kw",
    [
        {"far_date": NEAR_D},
        {"far_date": date(2025, 12, 1)},
        {"near": usd(0)},
        {"near": usd(-5)},
        {"storage_cost_annual_pct": Decimal(-1)},
        {"other_annual_costs_pct": {"x": Decimal(-1)}},
        {"fixed_costs": {"x": Decimal(-1)}},
        {"other_annual_costs_pct": {"guardado": Decimal(1)}},
        {"day_count_basis": 0},
    ],
)
def test_entradas_invalidas(kw):
    with pytest.raises(CarryInputError):
        base(**kw)


def test_rechaza_float():
    with pytest.raises(TypeError):
        base(storage_cost_annual_pct=10.5)
    with pytest.raises(TypeError):
        base(day_count_basis=365.0)


# ---------- warrant ----------
# 50 % financiado al 10 % anual: 400 * 0,5 * 0,10 * 0,2 = 4 de interés.
# Gastos de una vez 0,5 % de 400 = 2. Neto: 12 - 8 (guardado) - 4 - 2 = -2.


def terms(**kw):
    params = dict(
        financed_pct=Decimal(50), annual_rate_pct=Decimal(10),
        upfront_costs_pct={"comisión": Decimal("0.5")},
    )
    params.update(kw)
    return WarrantTerms(**params)


def test_warrant_suma_interes_y_gastos_al_costo():
    r = base(warrant=terms())
    assert r.warrant_interest == usd(4)
    assert r.warrant_upfront_total == usd(2)
    assert r.cost_breakdown["warrant: interés"] == usd(4)
    assert r.cost_breakdown["warrant: comisión"] == usd(2)
    assert r.total_cost == usd(14)
    assert r.net == usd(-2)
    assert r.total_annual_costs_pct == Decimal(15)  # 10 guardado + 5 interés
    assert r.net_annual_pct == Decimal("-2.5")  # 15 - 15 - 2,5 de gastos únicos


def test_sin_warrant_no_hay_campos_de_warrant():
    r = base()
    assert r.warrant_interest is None and r.warrant_upfront_total is None


def test_warrant_sin_financiar_no_cobra_interes():
    r = base(warrant=terms(financed_pct=Decimal(0), upfront_costs_pct={}))
    assert r.warrant_interest == usd(0)
    assert r.net == usd(4)


@pytest.mark.parametrize(
    "kw",
    [
        {"financed_pct": Decimal(101)},
        {"financed_pct": Decimal(-1)},
        {"annual_rate_pct": Decimal(-1)},
        {"upfront_costs_pct": {"x": Decimal(-1)}},
    ],
)
def test_warrant_entradas_invalidas(kw):
    with pytest.raises(CarryInputError):
        terms(**kw)


def test_warrant_rechaza_float():
    with pytest.raises(TypeError):
        terms(annual_rate_pct=10.5)


def test_prefijo_warrant_reservado():
    with pytest.raises(CarryInputError):
        base(warrant=terms(), fixed_costs={"warrant: otro": Decimal(1)})


# ---------- endpoint ----------

client = TestClient(app)
BODY = {
    "near_price": "400", "far_price": "412", "unit": "USD/t",
    "price_type": "settlement", "near_date": "2026-01-01", "far_date": "2026-03-15",
    "storage_cost_annual_pct": "10",
}


def test_endpoint_devuelve_el_calculo_con_decimales_como_texto():
    resp = client.post("/tools/carry", json=BODY)
    assert resp.status_code == 200
    data = resp.json()
    assert data["net"] == {"value": "4", "unit": "USD/t"} or Decimal(data["net"]["value"]) == 4
    assert Decimal(data["net_annual_pct"]) == 5
    assert data["days"] == 73
    assert data["price_type"] == "settlement"


def test_endpoint_responde_422_ante_fechas_invertidas():
    resp = client.post("/tools/carry", json={**BODY, "far_date": "2025-12-01"})
    assert resp.status_code == 422


def test_endpoint_exige_el_tipo_de_precio():
    body = {k: v for k, v in BODY.items() if k != "price_type"}
    assert client.post("/tools/carry", json=body).status_code == 422


def test_endpoint_con_warrant():
    body = {
        **BODY,
        "warrant": {
            "financed_pct": "50", "annual_rate_pct": "10",
            "upfront_costs_pct": {"comisión": "0.5"},
        },
    }
    data = client.post("/tools/carry", json=body).json()
    assert Decimal(data["net"]["value"]) == -2
    assert Decimal(data["warrant_interest"]["value"]) == 4
    assert Decimal(data["net_annual_pct"]) == Decimal("-2.5")


def test_endpoint_warrant_invalido_da_422():
    body = {**BODY, "warrant": {"financed_pct": "150", "annual_rate_pct": "10"}}
    assert client.post("/tools/carry", json=body).status_code == 422
