"""Relaciones entre dos series: razón (A/B) y diferencia (A - B).

Se calcula primero la relación y recién después se compara contra su historia
(``compare_to_history`` sobre la serie resultante).

Reglas:

* Las series se alinean por **fecha exacta**. Las fechas que están en una sola
  serie se descartan y se devuelven en el resultado (``only_in_first`` y
  ``only_in_second``): lo que falta se ve, no se rellena.
* Ambas series deben tener el mismo ``data_kind``: no se mezclan datos reales
  con de prueba o simulados.
* Ambas deben tener el mismo ``price_type`` (no se mezcla settlement con último,
  bid o ask). Para comparar a propósito dos tipos distintos (por ejemplo físico
  contra futuro) hay que pasar ``allow_mixed_price_types=True``; el resultado
  queda como ``UNSPECIFIED``.
* La **diferencia** exige la misma unidad (``UnitMismatchError``). No convierte
  nada: si hay que pasar de centavos por bushel a USD/t, o de pesos a dólares, se
  hace antes y de forma explícita (``app/instruments/units.py``).
* La **razón** entre unidades iguales da ``ratio``; entre unidades distintas
  da ``A/B`` como unidad derivada (sin conversión).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.analytics.series import Series
from app.instruments.price_types import PriceType
from app.instruments.units import UnitMismatchError


class DataKindMismatchError(ValueError):
    """Se intentó combinar series de distinto ``data_kind``."""


class PriceTypeMismatchError(ValueError):
    """Se intentó combinar precios de distinto tipo sin permitirlo."""


@dataclass(frozen=True)
class RelationResult:
    series: Series
    only_in_first: tuple[date, ...]
    only_in_second: tuple[date, ...]
    skipped_zero_denominator: tuple[date, ...] = ()


def _check_compatible(
    first: Series, second: Series, allow_mixed_price_types: bool
) -> PriceType:
    if first.data_kind is not second.data_kind:
        raise DataKindMismatchError(
            f"no se combinan datos {first.data_kind.value} con {second.data_kind.value}"
        )
    if first.price_type is not second.price_type:
        if not allow_mixed_price_types:
            raise PriceTypeMismatchError(
                f"tipos de precio distintos ({first.price_type.value} y "
                f"{second.price_type.value}); usar allow_mixed_price_types=True "
                "solo si la comparación es intencional"
            )
        return PriceType.UNSPECIFIED
    return first.price_type


def _align(first: Series, second: Series):
    a, b = first.as_dict(), second.as_dict()
    common = sorted(a.keys() & b.keys())
    only_a = tuple(sorted(a.keys() - b.keys()))
    only_b = tuple(sorted(b.keys() - a.keys()))
    return a, b, common, only_a, only_b


def spread(
    first: Series,
    second: Series,
    *,
    name: str,
    allow_mixed_price_types: bool = False,
) -> RelationResult:
    """``first - second`` en cada fecha común. Misma unidad obligatoria."""
    if first.unit != second.unit:
        raise UnitMismatchError(
            f"la diferencia exige la misma unidad: {first.unit} vs {second.unit}"
        )
    price_type = _check_compatible(first, second, allow_mixed_price_types)
    a, b, common, only_a, only_b = _align(first, second)
    result = Series.from_pairs(
        name=name,
        unit=first.unit,
        data_kind=first.data_kind,
        source=f"derivada: {first.source} - {second.source}",
        price_type=price_type,
        pairs=[(d, a[d] - b[d]) for d in common],
    )
    return RelationResult(result, only_a, only_b)


def ratio(
    numerator: Series,
    denominator: Series,
    *,
    name: str,
    allow_mixed_price_types: bool = False,
) -> RelationResult:
    """``numerator / denominator`` en cada fecha común.

    Las fechas con denominador cero se omiten y se informan en
    ``skipped_zero_denominator``.
    """
    price_type = _check_compatible(numerator, denominator, allow_mixed_price_types)
    a, b, common, only_a, only_b = _align(numerator, denominator)
    pairs: list[tuple[date, Decimal]] = []
    zero: list[date] = []
    for d in common:
        if b[d] == 0:
            zero.append(d)
        else:
            pairs.append((d, a[d] / b[d]))
    unit = "ratio" if numerator.unit == denominator.unit else (
        f"{numerator.unit}/{denominator.unit}"
    )
    result = Series.from_pairs(
        name=name,
        unit=unit,
        data_kind=numerator.data_kind,
        source=f"derivada: {numerator.source} / {denominator.source}",
        price_type=price_type,
        pairs=pairs,
    )
    return RelationResult(result, only_a, only_b, tuple(zero))
