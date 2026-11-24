"""Cálculo ESTIMADO del último día de negociación de un contrato.

Aplica la regla de vencimiento publicada por cada mercado sobre un calendario
de días hábiles. Importante:

* El resultado es una ESTIMACIÓN basada en la regla, no la fecha oficial. La
  fecha oficial la publican A3 y CME en sus calendarios y circulares.
* Este módulo NO incluye feriados: no se verificó ningún calendario oficial.
  Solo conoce sábados y domingos. Quien llama pasa los feriados del mercado
  correspondiente (Argentina para A3, EE.UU./CME para CBOT) en ``holidays``.
  Sin feriados, las fechas cercanas a un feriado pueden salir mal.
"""

import calendar
from collections.abc import Collection
from datetime import date, timedelta

from app.instruments.contracts import ContractSpec, ExpiryRule


def is_business_day(day: date, holidays: Collection[date] = ()) -> bool:
    return day.weekday() < 5 and day not in holidays


def _check_month(year: int, month: int) -> None:
    if not 1 <= month <= 12:
        raise ValueError(f"mes inválido: {month}")
    if year < 1:
        raise ValueError(f"año inválido: {year}")


def business_day_before_15th(
    year: int, month: int, holidays: Collection[date] = ()
) -> date:
    """CBOT: el día hábil anterior al día 15 calendario del mes."""
    _check_month(year, month)
    day = date(year, month, 14)
    while not is_business_day(day, holidays):
        day -= timedelta(days=1)
    return day


def session_before_last_five(
    year: int, month: int, holidays: Collection[date] = ()
) -> date:
    """A3 con entrega: la última rueda previa a las últimas cinco ruedas del mes."""
    _check_month(year, month)
    last_day = calendar.monthrange(year, month)[1]
    business_days = [
        date(year, month, d)
        for d in range(1, last_day + 1)
        if is_business_day(date(year, month, d), holidays)
    ]
    if len(business_days) < 6:
        raise ValueError(f"el mes {year}-{month:02d} tiene menos de 6 días hábiles")
    return business_days[-6]


def last_business_day_of_previous_month(
    year: int, month: int, holidays: Collection[date] = ()
) -> date:
    """A3 Índice Mini: el último día hábil del mes anterior al mes del contrato."""
    _check_month(year, month)
    first_of_month = date(year, month, 1)
    day = first_of_month - timedelta(days=1)
    while not is_business_day(day, holidays):
        day -= timedelta(days=1)
    return day


def estimate_last_trading_day(
    spec: ContractSpec,
    year: int,
    month: int,
    holidays: Collection[date] = (),
) -> date:
    """Estima el último día de negociación del contrato de ``year``/``month``.

    ValueError si el contrato no se lista en ese mes. NotImplementedError si la
    regla del contrato no se calcula en este módulo.
    """
    _check_month(year, month)
    if spec.months is not None and month not in spec.months:
        raise ValueError(
            f"{spec.key} no lista el mes {month} (meses: {list(spec.months)})"
        )

    rule = spec.expiry_rule
    if rule is ExpiryRule.BUSINESS_DAY_BEFORE_15TH:
        return business_day_before_15th(year, month, holidays)
    if rule is ExpiryRule.SESSION_BEFORE_LAST_FIVE_OF_MONTH:
        return session_before_last_five(year, month, holidays)
    if rule is ExpiryRule.LAST_BUSINESS_DAY_OF_PREVIOUS_MONTH:
        return last_business_day_of_previous_month(year, month, holidays)
    raise NotImplementedError(
        f"La regla de vencimiento de {spec.key} ({rule.value}) no se calcula "
        "en este módulo."
    )
