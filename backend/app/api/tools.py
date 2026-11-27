"""Endpoints de herramientas (calculadoras).

Los valores decimales se devuelven como texto para no perder precisión.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.calculators import CarryInputError, calculate_carry
from app.instruments import PriceType, PriceUnit, Price, UnitMismatchError

router = APIRouter(prefix="/tools", tags=["tools"])


class CarryRequest(BaseModel):
    near_price: Decimal = Field(description="Precio del vencimiento cercano")
    far_price: Decimal = Field(description="Precio del vencimiento lejano")
    unit: PriceUnit = Field(description="Unidad de AMBOS precios (no se convierte)")
    price_type: PriceType = Field(
        description="Tipo de ambos precios: settlement, last, bid, ask o unspecified"
    )
    near_date: date
    far_date: date
    storage_cost_annual_pct: Decimal = Field(
        description="Costo de guardado, % anual simple (12 = 12 %)"
    )
    other_annual_costs_pct: dict[str, Decimal] = Field(
        default_factory=dict,
        description="Otros costos en % anual simple, por concepto (ej. financiación)",
    )
    fixed_costs: dict[str, Decimal] = Field(
        default_factory=dict,
        description="Costos fijos del período, en la unidad del precio, por concepto",
    )
    day_count_basis: int = Field(default=365, description="Base de días del año")


class AmountOut(BaseModel):
    value: Decimal
    unit: str


class CarryResponse(BaseModel):
    pase: AmountOut
    days: int
    day_count_basis: int
    pase_pct: Decimal
    pase_annualized_pct: Decimal
    total_annual_costs_pct: Decimal
    carry_cost: AmountOut
    fixed_costs_total: AmountOut
    total_cost: AmountOut
    net: AmountOut
    net_annual_pct: Decimal
    price_type: PriceType
    cost_breakdown: dict[str, AmountOut]


def _amount(price: Price) -> AmountOut:
    return AmountOut(value=price.value, unit=price.unit.value)


@router.post("/carry", response_model=CarryResponse)
def carry(request: CarryRequest) -> CarryResponse:
    """Pase contra costo de guardado. Muestra números; no recomienda operar."""
    try:
        r = calculate_carry(
            near=Price(request.near_price, request.unit),
            far=Price(request.far_price, request.unit),
            near_date=request.near_date,
            far_date=request.far_date,
            price_type=request.price_type,
            storage_cost_annual_pct=request.storage_cost_annual_pct,
            other_annual_costs_pct=request.other_annual_costs_pct,
            fixed_costs=request.fixed_costs,
            day_count_basis=request.day_count_basis,
        )
    except (CarryInputError, UnitMismatchError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CarryResponse(
        pase=_amount(r.pase),
        days=r.days,
        day_count_basis=r.day_count_basis,
        pase_pct=r.pase_pct,
        pase_annualized_pct=r.pase_annualized_pct,
        total_annual_costs_pct=r.total_annual_costs_pct,
        carry_cost=_amount(r.carry_cost),
        fixed_costs_total=_amount(r.fixed_costs_total),
        total_cost=_amount(r.total_cost),
        net=_amount(r.net),
        net_annual_pct=r.net_annual_pct,
        price_type=r.price_type,
        cost_breakdown={k: _amount(v) for k, v in r.cost_breakdown.items()},
    )
