"""Comparador estacional: un dato contra su historia de la misma fecha.

Definición de "misma fecha" (acordada con el usuario el 2026-11-27): **la misma
fecha de calendario** (mismo día y mes) en cada año anterior. No es "mismo día
de campaña".

Decisiones explícitas:

* **Sin interpolación.** Si en un año no hay observación para esa fecha, el año
  figura como faltante con su motivo. Con ``tolerance_days > 0`` se acepta la
  observación más reciente anterior dentro de esa ventana (útil para fines de
  semana y feriados) y se informa qué fecha real se usó. Nunca se mira hacia
  adelante.
* **29 de febrero.** Si ``as_of`` es 29/2, los años no bisiestos no tienen esa
  fecha y quedan como faltantes (``NO_SUCH_DATE``); no se reemplaza por el 28/2.
* **Sin años propios.** Los años comparados son los ``years_back`` anteriores
  al de ``as_of``; el año corriente no entra en las estadísticas.
* **Percentil.** Rango "mid-rank": (cantidad de valores previos menores +
  la mitad de los iguales) / cantidad de valores previos × 100.
* **Desvío.** Desvío estándar muestral (n-1); necesita al menos 2 años con dato.
* Los años con dato son pocos: el resultado muestra ``count`` para que se vea
  cuán débil o sólida es la comparación.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from app.analytics.series import DataKind, Series
from app.instruments.price_types import PriceType


class MissingReason(str, Enum):
    NO_SUCH_DATE = "no_such_date"  # la fecha no existe ese año (29/2)
    NO_OBSERVATION = "no_observation"  # la serie no tiene dato en la ventana


class NoCurrentObservationError(ValueError):
    """No hay observación actual para ``as_of`` (ni dentro de la tolerancia)."""


@dataclass(frozen=True)
class YearComparison:
    year: int
    target_date: date | None  # None cuando la fecha no existe ese año
    observation_date: date | None  # fecha real de la observación usada
    value: Decimal | None
    missing_reason: MissingReason | None

    @property
    def lag_days(self) -> int | None:
        """Días entre la fecha pedida y la observación usada (0 si es exacta)."""
        if self.target_date is None or self.observation_date is None:
            return None
        return (self.target_date - self.observation_date).days


@dataclass(frozen=True)
class SeasonalStats:
    count: int
    mean: Decimal
    median: Decimal
    minimum: Decimal
    maximum: Decimal
    stdev: Decimal | None  # None con menos de 2 valores


@dataclass(frozen=True)
class SeasonalComparison:
    series_name: str
    unit: str
    data_kind: DataKind
    price_type: PriceType
    source: str
    as_of: date
    tolerance_days: int
    current_date: date  # fecha real de la observación actual
    current_value: Decimal
    years: tuple[YearComparison, ...]
    stats: SeasonalStats | None  # None si ningún año tiene dato
    diff_vs_mean: Decimal | None
    pct_diff_vs_mean: Decimal | None  # None si el promedio es 0
    z_score: Decimal | None  # None si no hay desvío o es 0
    percentile_rank: Decimal | None  # 0 a 100


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal(2)


def _stats(values: list[Decimal]) -> SeasonalStats:
    n = len(values)
    mean = sum(values, Decimal(0)) / Decimal(n)
    stdev: Decimal | None = None
    if n >= 2:
        variance = sum(((v - mean) ** 2 for v in values), Decimal(0)) / Decimal(n - 1)
        stdev = variance.sqrt()
    return SeasonalStats(
        count=n,
        mean=mean,
        median=_median(values),
        minimum=min(values),
        maximum=max(values),
        stdev=stdev,
    )


def compare_to_history(
    series: Series,
    as_of: date,
    *,
    years_back: int,
    tolerance_days: int = 0,
) -> SeasonalComparison:
    """Compara el valor de ``as_of`` con el de la misma fecha de los
    ``years_back`` años anteriores."""
    if years_back < 1:
        raise ValueError("years_back debe ser al menos 1")
    if tolerance_days < 0:
        raise ValueError("tolerance_days no puede ser negativo")

    current = series.lookup(as_of, tolerance_days)
    if current is None:
        raise NoCurrentObservationError(
            f"la serie '{series.name}' no tiene dato para {as_of.isoformat()}"
            f" (tolerancia {tolerance_days} días)"
        )
    current_date, current_value = current

    years: list[YearComparison] = []
    for year in range(as_of.year - years_back, as_of.year):
        try:
            target = date(year, as_of.month, as_of.day)
        except ValueError:  # 29/2 en año no bisiesto
            years.append(
                YearComparison(year, None, None, None, MissingReason.NO_SUCH_DATE)
            )
            continue
        found = series.lookup(target, tolerance_days)
        if found is None:
            years.append(
                YearComparison(year, target, None, None, MissingReason.NO_OBSERVATION)
            )
        else:
            years.append(YearComparison(year, target, found[0], found[1], None))

    prior = [y.value for y in years if y.value is not None]
    stats = _stats(prior) if prior else None

    diff = pct = z = rank = None
    if stats is not None:
        diff = current_value - stats.mean
        if stats.mean != 0:
            pct = diff / stats.mean * Decimal(100)
        if stats.stdev is not None and stats.stdev != 0:
            z = diff / stats.stdev
        below = sum(1 for v in prior if v < current_value)
        equal = sum(1 for v in prior if v == current_value)
        rank = (Decimal(below) + Decimal(equal) / Decimal(2)) / Decimal(
            len(prior)
        ) * Decimal(100)

    return SeasonalComparison(
        series_name=series.name,
        unit=series.unit,
        data_kind=series.data_kind,
        price_type=series.price_type,
        source=series.source,
        as_of=as_of,
        tolerance_days=tolerance_days,
        current_date=current_date,
        current_value=current_value,
        years=tuple(years),
        stats=stats,
        diff_vs_mean=diff,
        pct_diff_vs_mean=pct,
        z_score=z,
        percentile_rank=rank,
    )
