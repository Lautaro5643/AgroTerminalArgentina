"""Especificaciones de los contratos de futuros de soja.

Cada contrato cita la fuente de la que se tomó cada dato y deja explícito lo
que NO se pudo confirmar. Consultado el 2026-11-23. Detalle y limitaciones en
docs/especificaciones-contratos.md.

Alcance: solo soja (decisión del proyecto: soja primero). No se modelan los
contratos en pesos ni los de maíz y trigo.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.instruments.units import (
    Commodity,
    PriceUnit,
    bushels_to_tonnes,
)

CHECKED_ON = "2026-11-23"


class SizeUnit(str, Enum):
    BUSHEL = "bushel"
    TONNE = "tonne"


class Settlement(str, Enum):
    PHYSICAL = "physical"  # entrega física
    CASH = "cash"  # liquidación por diferencias en efectivo


class ExpiryRule(str, Enum):
    # CBOT: "el día hábil anterior al día 15 calendario del mes del contrato".
    BUSINESS_DAY_BEFORE_15TH = "business_day_before_15th"
    # A3 con entrega: "la última rueda previa a las últimas cinco ruedas del
    # mes pactado para la entrega".
    SESSION_BEFORE_LAST_FIVE_OF_MONTH = "session_before_last_five_of_month"
    # A3 Índice Mini: "el último día hábil del mes anterior al mes del contrato".
    LAST_BUSINESS_DAY_OF_PREVIOUS_MONTH = "last_business_day_of_previous_month"
    # A3 Soja Chicago: el día del vencimiento de las opciones sobre futuros de
    # soja CBOT. Se cita la regla pero NO se calcula (requiere el calendario
    # de vencimiento de opciones de CME).
    CBOT_SOY_OPTIONS_EXPIRY = "cbot_soy_options_expiry"


@dataclass(frozen=True)
class ContractSpec:
    key: str
    exchange: str
    name: str
    commodity: Commodity
    size: Decimal
    size_unit: SizeUnit
    price_unit: PriceUnit
    settlement: Settlement
    expiry_rule: ExpiryRule
    # Meses de contrato (1-12). None = "todos los meses" según el documento
    # citado (los meses efectivamente listados pueden ser menos).
    months: tuple[int, ...] | None
    # Fluctuación mínima en la unidad de precio. None = no figura en la fuente.
    tick: Decimal | None
    source_url: str
    source_note: str
    caveats: tuple[str, ...] = ()

    def size_in_tonnes(self) -> Decimal:
        """Tamaño del contrato en toneladas métricas (conversión explícita)."""
        if self.size_unit is SizeUnit.TONNE:
            return self.size
        return bushels_to_tonnes(self.commodity, self.size)


CBOT_ZS = ContractSpec(
    key="CBOT_ZS",
    exchange="CBOT (CME Group)",
    name="Soybean futures (ZS)",
    commodity=Commodity.SOYBEAN,
    size=Decimal(5000),
    size_unit=SizeUnit.BUSHEL,
    price_unit=PriceUnit.USC_PER_BUSHEL,
    settlement=Settlement.PHYSICAL,
    expiry_rule=ExpiryRule.BUSINESS_DAY_BEFORE_15TH,
    months=(1, 3, 5, 7, 8, 9, 11),
    tick=Decimal("0.25"),  # 1/4 de centavo por bushel (US$12,50 por contrato)
    source_url=(
        "https://www.cmegroup.com/cn-t/markets/agriculture/oilseeds/"
        "soybean.contractSpecs.html"
    ),
    source_note=(
        "Página de especificaciones de CME (versión en chino) y, como segunda "
        "fuente coincidente, https://www.marketswiki.com/wiki/Soybean_futures"
    ),
    caveats=(
        "El último día de negociación depende del calendario de días hábiles "
        "de CBOT, que este módulo no incluye.",
    ),
)

# Letras de mes de los contratos CBOT de soja (informadas por CME).
CBOT_ZS_MONTH_CODES: dict[int, str] = {
    1: "F",
    3: "H",
    5: "K",
    7: "N",
    8: "Q",
    9: "U",
    11: "X",
}

_A3_GUIDE = "https://matbarofex.com.ar/documentos/investigacion/guia-de-negociacion-productos-agro"
_A3_CAVEAT_GUIDE = (
    "La guía de negociación usa ejemplos de 2021-2022: confirmar que la "
    "especificación siga vigente (circulares de A3)."
)
_A3_CAVEAT_MONTHS = (
    "La guía dice 'todos los meses'; los meses efectivamente listados pueden "
    "ser menos."
)
_A3_CAVEAT_CALENDAR = (
    "El vencimiento depende del calendario de ruedas de A3, que este módulo "
    "no incluye."
)

A3_SOJA_USD = ContractSpec(
    key="A3_SOJA_USD",
    exchange="A3 Mercados (Matba Rofex)",
    name="Soja en dólares (entrega física)",
    commodity=Commodity.SOYBEAN,
    size=Decimal(100),
    size_unit=SizeUnit.TONNE,
    price_unit=PriceUnit.USD_PER_TONNE,
    settlement=Settlement.PHYSICAL,
    expiry_rule=ExpiryRule.SESSION_BEFORE_LAST_FIVE_OF_MONTH,
    months=None,
    tick=None,
    source_url=_A3_GUIDE,
    source_note="Guía de negociación de productos agro de A3 (tabla de contratos).",
    caveats=(_A3_CAVEAT_GUIDE, _A3_CAVEAT_MONTHS, _A3_CAVEAT_CALENDAR),
)

A3_SOJA_MINI = ContractSpec(
    key="A3_SOJA_MINI",
    exchange="A3 Mercados (Matba Rofex)",
    name="Soja Índice Mini (liquidación en efectivo)",
    commodity=Commodity.SOYBEAN,
    size=Decimal(10),
    size_unit=SizeUnit.TONNE,
    price_unit=PriceUnit.USD_PER_TONNE,
    settlement=Settlement.CASH,
    expiry_rule=ExpiryRule.LAST_BUSINESS_DAY_OF_PREVIOUS_MONTH,
    months=None,
    tick=None,  # el reglamento dice que se informa por Circular
    source_url="https://matbarofex.com.ar/documentos/legales/reglamento-soja-mini",
    source_note=(
        "Reglamento del contrato (arts. 2, 3, 4, 6, 7 y 10). Liquida por "
        "diferencia contra el precio de ajuste del futuro de Soja en Dólares "
        "del mismo mes; los cobros y pagos se hacen en pesos al tipo de "
        "cambio de referencia del Mercado."
    ),
    caveats=(
        "La fluctuación mínima 'será informada mediante Circular': no figura.",
        _A3_CAVEAT_MONTHS,
        _A3_CAVEAT_CALENDAR,
    ),
)

A3_SOJA_CHICAGO = ContractSpec(
    key="A3_SOJA_CHICAGO",
    exchange="A3 Mercados (Matba Rofex)",
    name="Soja Chicago (liquidación en efectivo)",
    commodity=Commodity.SOYBEAN,
    size=Decimal(5),
    size_unit=SizeUnit.TONNE,
    price_unit=PriceUnit.USD_PER_TONNE,
    settlement=Settlement.CASH,
    expiry_rule=ExpiryRule.CBOT_SOY_OPTIONS_EXPIRY,
    months=None,
    tick=None,
    source_url=_A3_GUIDE,
    source_note="Guía de negociación de productos agro de A3 (tabla de contratos).",
    caveats=(
        _A3_CAVEAT_GUIDE,
        _A3_CAVEAT_MONTHS,
        "Vence el día del vencimiento de las opciones sobre futuros de soja "
        "CBOT; esa fecha NO se calcula en este módulo.",
        "No se verificó de dónde toma el precio de referencia.",
    ),
)

SOYBEAN_CONTRACTS: dict[str, ContractSpec] = {
    spec.key: spec for spec in (CBOT_ZS, A3_SOJA_USD, A3_SOJA_MINI, A3_SOJA_CHICAGO)
}


def get_contract(key: str) -> ContractSpec:
    """Devuelve la especificación del contrato. KeyError si no existe."""
    try:
        return SOYBEAN_CONTRACTS[key]
    except KeyError:
        raise KeyError(
            f"Contrato desconocido: {key!r}. Disponibles: {sorted(SOYBEAN_CONTRACTS)}"
        ) from None
