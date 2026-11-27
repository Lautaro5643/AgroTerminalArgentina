"""Calculadora de pase contra costo de guardado (embolsar, financiar, etc.).

El pase es la diferencia entre el precio del vencimiento lejano y el del
cercano. La herramienta lo lee contra los costos que **carga el usuario** y
devuelve el neto. No recomienda operar: muestra números.

Convenciones (todas visibles en el resultado, ninguna escondida):

* ``pase = lejano - cercano``. Misma unidad y mismo tipo de precio
  (settlement con settlement, último con último...). Si no coinciden, falla.
* ``dias`` = días corridos entre ambos vencimientos (``far_date - near_date``).
* ``pase_pct = pase / cercano * 100``.
* ``pase_anualizado_pct = pase_pct * base / dias`` (interés simple; la base por
  defecto es 365 y es un parámetro).
* Costos anuales (``storage_cost_annual_pct`` y ``other_annual_costs_pct``):
  porcentaje anual **simple** sobre el precio cercano. ``12`` significa 12 %.
  Costo del período = ``cercano * pct / 100 * dias / base``.
* Costos fijos (``fixed_costs``): importes en la misma unidad que el precio,
  para todo el período.
* ``neto = pase - costos del período - costos fijos``.
* ``neto_anual_pct = neto / cercano * base / dias * 100``. Sin costos fijos es
  igual a ``pase_anualizado_pct - suma de costos anuales``.

No hay valores por defecto para ningún costo: el material oficial leído no
informa porcentajes financiados, tasas ni comisiones típicas. Todo lo carga el
usuario. No hay conversión de moneda ni de unidad.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.instruments.price_types import PriceType
from app.instruments.units import Price, UnitMismatchError, as_decimal

HUNDRED = Decimal(100)


class CarryInputError(ValueError):
    """Datos de entrada inválidos para la calculadora."""


class PriceTypeMismatchError(CarryInputError):
    """Los dos precios no son del mismo tipo."""


@dataclass(frozen=True)
class CarryResult:
    pase: Price
    days: int
    day_count_basis: int
    pase_pct: Decimal
    pase_annualized_pct: Decimal
    total_annual_costs_pct: Decimal
    carry_cost: Price  # costos anuales llevados al período
    fixed_costs_total: Price
    total_cost: Price
    net: Price
    net_annual_pct: Decimal
    price_type: PriceType
    # Detalle por concepto, en la unidad del precio y para todo el período.
    cost_breakdown: dict[str, Price] = field(default_factory=dict)


def _validate_costs(costs: Mapping[str, Decimal | int] | None, what: str):
    clean: dict[str, Decimal] = {}
    for label, value in (costs or {}).items():
        if not label.strip():
            raise CarryInputError(f"{what}: el nombre del concepto no puede estar vacío")
        number = as_decimal(value, label)
        if number < 0:
            raise CarryInputError(f"{what}: '{label}' no puede ser negativo")
        clean[label] = number
    return clean


def calculate_carry(
    *,
    near: Price,
    far: Price,
    near_date: date,
    far_date: date,
    price_type: PriceType,
    storage_cost_annual_pct: Decimal | int,
    other_annual_costs_pct: Mapping[str, Decimal | int] | None = None,
    fixed_costs: Mapping[str, Decimal | int] | None = None,
    day_count_basis: int = 365,
    far_price_type: PriceType | None = None,
) -> CarryResult:
    """Calcula el pase y su neto contra los costos cargados por el usuario.

    ``price_type`` es el tipo del precio cercano; ``far_price_type`` el del
    lejano (si se omite, se asume igual). Si difieren se rechaza.
    """
    if far_price_type is not None and far_price_type is not price_type:
        raise PriceTypeMismatchError(
            f"el pase exige el mismo tipo de precio: {price_type.value} vs "
            f"{far_price_type.value}"
        )
    if near.unit is not far.unit:
        raise UnitMismatchError(
            f"los dos precios deben estar en la misma unidad: {near.unit.value} "
            f"vs {far.unit.value}"
        )
    if near.value <= 0:
        raise CarryInputError("el precio cercano debe ser mayor que cero")
    days = (far_date - near_date).days
    if days <= 0:
        raise CarryInputError("el vencimiento lejano debe ser posterior al cercano")
    if isinstance(day_count_basis, bool) or not isinstance(day_count_basis, int):
        raise TypeError("day_count_basis debe ser int")
    if day_count_basis <= 0:
        raise CarryInputError("day_count_basis debe ser mayor que cero")

    storage = _validate_costs({"guardado": storage_cost_annual_pct}, "costo anual")[
        "guardado"
    ]
    others = _validate_costs(other_annual_costs_pct, "costos anuales")
    fixed = _validate_costs(fixed_costs, "costos fijos")
    if "guardado" in others:
        raise CarryInputError("'guardado' está reservado para storage_cost_annual_pct")

    unit = near.unit
    period = Decimal(days) / Decimal(day_count_basis)
    basis = Decimal(day_count_basis)

    breakdown: dict[str, Price] = {}
    for label, pct in {"guardado": storage, **others}.items():
        breakdown[label] = Price(near.value * pct / HUNDRED * period, unit)
    annual_total = storage + sum(others.values(), Decimal(0))
    carry_cost = sum((p.value for p in breakdown.values()), Decimal(0))

    fixed_total = Decimal(0)
    for label, amount in fixed.items():
        if label in breakdown:
            raise CarryInputError(f"concepto repetido: '{label}'")
        breakdown[label] = Price(amount, unit)
        fixed_total += amount

    pase_value = far.value - near.value
    total_cost = carry_cost + fixed_total
    net = pase_value - total_cost
    pase_pct = pase_value / near.value * HUNDRED

    return CarryResult(
        pase=Price(pase_value, unit),
        days=days,
        day_count_basis=day_count_basis,
        pase_pct=pase_pct,
        pase_annualized_pct=pase_pct * basis / Decimal(days),
        total_annual_costs_pct=annual_total,
        carry_cost=Price(carry_cost, unit),
        fixed_costs_total=Price(fixed_total, unit),
        total_cost=Price(total_cost, unit),
        net=Price(net, unit),
        net_annual_pct=net / near.value * basis / Decimal(days) * HUNDRED,
        price_type=price_type,
        cost_breakdown=breakdown,
    )
