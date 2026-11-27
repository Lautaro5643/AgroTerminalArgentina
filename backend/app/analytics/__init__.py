"""Análisis: series, comparador estacional y relaciones."""

from app.analytics.relations import (
    DataKindMismatchError,
    PriceTypeMismatchError,
    RelationResult,
    ratio,
    spread,
)
from app.analytics.seasonal import (
    MissingReason,
    NoCurrentObservationError,
    SeasonalComparison,
    SeasonalStats,
    YearComparison,
    compare_to_history,
)
from app.analytics.series import DataKind, Series, SeriesError

__all__ = [
    "DataKind",
    "DataKindMismatchError",
    "MissingReason",
    "NoCurrentObservationError",
    "PriceTypeMismatchError",
    "RelationResult",
    "SeasonalComparison",
    "SeasonalStats",
    "Series",
    "SeriesError",
    "YearComparison",
    "compare_to_history",
    "ratio",
    "spread",
]
