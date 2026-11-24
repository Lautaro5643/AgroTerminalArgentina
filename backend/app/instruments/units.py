"""Unidades y conversiones de granos.

Regla del proyecto: sin conversiones implícitas. Toda conversión pasa por una
función de este módulo, con unidades explícitas, y nada se redondea acá:
quien llama decide cuántos decimales usar.

Valores y fuentes (consultadas el 2026-11-23, ver docs/especificaciones-contratos.md):

* Libras por bushel: soja 60, trigo 60, maíz 56. Fuente consultada: tabla de
  conversión del U.S. Grains Council (https://grains.org/?p=429), que no cita
  fuente primaria. NO se pudo confirmar contra el manual USDA AH-697.
  Verificación cruzada disponible: CME informa que un contrato de soja de
  5.000 bushels equivale a "aprox. 136 toneladas métricas", lo que es
  coherente con 60 lb/bushel.
* 1 libra = 0,45359237 kg: valor exacto por definición internacional.
* Con esos dos valores se reproducen las cifras del Grains Council:
  36,7437 bushels/t (soja y trigo) y 39,368 bushels/t (maíz).

Se usa Decimal y no float para que los resultados sean reproducibles y sin
errores de representación. Los float se rechazan a propósito.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

POUND_IN_KG = Decimal("0.45359237")
KG_PER_TONNE = Decimal(1000)


class Commodity(str, Enum):
    SOYBEAN = "soybean"
    CORN = "corn"
    WHEAT = "wheat"


# Libras por bushel estándar (ver encabezado para la fuente y su limitación).
POUNDS_PER_BUSHEL: dict[Commodity, Decimal] = {
    Commodity.SOYBEAN: Decimal(60),
    Commodity.CORN: Decimal(56),
    Commodity.WHEAT: Decimal(60),
}


class PriceUnit(str, Enum):
    USC_PER_BUSHEL = "USc/bu"  # centavos de dólar por bushel (CBOT)
    USD_PER_TONNE = "USD/t"  # dólares por tonelada métrica (A3)


class UnitError(ValueError):
    """Error de unidades."""


class UnitMismatchError(UnitError):
    """Se intentó convertir un precio que no está en la unidad esperada."""


def _as_decimal(value: object, name: str = "valor") -> Decimal:
    """Acepta Decimal o int. Rechaza float (impreciso), bool y texto."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise TypeError(
            f"{name} debe ser Decimal o int, no {type(value).__name__}: "
            "los float no se aceptan por su imprecisión"
        )
    return Decimal(value)


@dataclass(frozen=True)
class Price:
    """Un precio con su unidad explícita."""

    value: Decimal
    unit: PriceUnit

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _as_decimal(self.value, "value"))
        if not isinstance(self.unit, PriceUnit):
            raise TypeError("unit debe ser un PriceUnit")


def tonnes_per_bushel(commodity: Commodity) -> Decimal:
    """Toneladas métricas que pesa un bushel del grano."""
    return POUNDS_PER_BUSHEL[commodity] * POUND_IN_KG / KG_PER_TONNE


def bushels_per_tonne(commodity: Commodity) -> Decimal:
    """Bushels que hay en una tonelada métrica del grano."""
    return Decimal(1) / tonnes_per_bushel(commodity)


def bushels_to_tonnes(commodity: Commodity, bushels: Decimal | int) -> Decimal:
    return _as_decimal(bushels, "bushels") * tonnes_per_bushel(commodity)


def tonnes_to_bushels(commodity: Commodity, tonnes: Decimal | int) -> Decimal:
    return _as_decimal(tonnes, "tonnes") * bushels_per_tonne(commodity)


def usc_per_bushel_to_usd_per_tonne(commodity: Commodity, price: Price) -> Price:
    """Centavos por bushel -> dólares por tonelada. Acepta valores negativos
    (por ejemplo, un spread)."""
    if price.unit is not PriceUnit.USC_PER_BUSHEL:
        raise UnitMismatchError(
            f"se esperaba {PriceUnit.USC_PER_BUSHEL.value} y llegó {price.unit.value}"
        )
    usd_per_bushel = price.value / Decimal(100)
    return Price(usd_per_bushel * bushels_per_tonne(commodity), PriceUnit.USD_PER_TONNE)


def usd_per_tonne_to_usc_per_bushel(commodity: Commodity, price: Price) -> Price:
    """Dólares por tonelada -> centavos por bushel."""
    if price.unit is not PriceUnit.USD_PER_TONNE:
        raise UnitMismatchError(
            f"se esperaba {PriceUnit.USD_PER_TONNE.value} y llegó {price.unit.value}"
        )
    usd_per_bushel = price.value * tonnes_per_bushel(commodity)
    return Price(usd_per_bushel * Decimal(100), PriceUnit.USC_PER_BUSHEL)
