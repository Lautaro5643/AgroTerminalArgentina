"""Tipos de precio.

Regla del proyecto: no se mezclan settlement (ajuste), último operado, bid y
ask. Toda serie y todo cálculo declara de qué tipo es el precio, y las
operaciones entre precios exigen que coincidan.

``UNSPECIFIED`` es para datos cuyo tipo no está confirmado (por ejemplo, la
pizarra de la BCR hasta ver datos reales). Dos precios ``UNSPECIFIED`` se
consideran del mismo tipo solo porque no se sabe nada más: es una limitación
declarada, no una garantía.
"""

from enum import Enum


class PriceType(str, Enum):
    SETTLEMENT = "settlement"  # precio de ajuste / cierre oficial del mercado
    LAST = "last"  # último operado
    BID = "bid"  # punta compradora
    ASK = "ask"  # punta vendedora
    UNSPECIFIED = "unspecified"  # tipo no confirmado
