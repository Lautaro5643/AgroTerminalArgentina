"""Series de tiempo con trazabilidad.

Una ``Series`` es una colección de observaciones (fecha, valor) que además
declara cuatro cosas que nunca se pierden en un cálculo:

* ``unit``: la unidad del valor (por ejemplo ``USD/t``).
* ``price_type``: settlement, último, bid, ask o sin especificar.
* ``data_kind``: si el dato es real, histórico, de prueba o simulado.
* ``source``: de dónde salió.

Reglas: los valores son ``Decimal`` (los ``float`` se rechazan), no se
interpola nada y una fecha sin observación sigue siendo una fecha sin
observación.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum

from app.instruments.price_types import PriceType
from app.instruments.units import as_decimal


class DataKind(str, Enum):
    REAL = "real"  # dato real y reciente de la fuente
    HISTORICAL = "historical"  # dato real, ya cerrado, cargado como historia
    TEST = "test"  # dato de prueba inventado para tests
    SIMULATED = "simulated"  # dato generado por un modelo o simulación


class SeriesError(ValueError):
    """Error de construcción de una serie."""


@dataclass(frozen=True)
class Series:
    name: str
    unit: str
    data_kind: DataKind
    source: str
    price_type: PriceType
    observations: tuple[tuple[date, Decimal], ...]

    @classmethod
    def from_pairs(
        cls,
        *,
        name: str,
        unit: str,
        data_kind: DataKind,
        source: str,
        price_type: PriceType,
        pairs: Iterable[tuple[date, Decimal | int]],
    ) -> "Series":
        """Arma una serie ordenada por fecha. Falla si hay fechas repetidas."""
        if not name.strip() or not unit.strip() or not source.strip():
            raise SeriesError("name, unit y source no pueden estar vacíos")
        if not isinstance(data_kind, DataKind):
            raise TypeError("data_kind debe ser un DataKind")
        if not isinstance(price_type, PriceType):
            raise TypeError("price_type debe ser un PriceType")
        seen: dict[date, Decimal] = {}
        for day, value in pairs:
            if isinstance(day, datetime) or not isinstance(day, date):
                raise TypeError("las fechas deben ser date (no datetime ni texto)")
            if day in seen:
                raise SeriesError(f"fecha repetida en la serie: {day.isoformat()}")
            seen[day] = as_decimal(value, "value")
        return cls(
            name=name,
            unit=unit,
            data_kind=data_kind,
            source=source,
            price_type=price_type,
            observations=tuple(sorted(seen.items())),
        )

    def __len__(self) -> int:
        return len(self.observations)

    def as_dict(self) -> dict[date, Decimal]:
        return dict(self.observations)

    def lookup(
        self, target: date, tolerance_days: int = 0
    ) -> tuple[date, Decimal] | None:
        """Observación de ``target`` o, si no hay, la más reciente anterior.

        Solo mira hacia atrás y como mucho ``tolerance_days`` días: nunca usa
        un dato posterior a la fecha pedida. Con ``tolerance_days=0`` exige la
        fecha exacta. Devuelve ``None`` si no hay nada: no se inventa un valor.
        La fecha devuelta es la de la observación real, que puede diferir de
        ``target``.
        """
        if tolerance_days < 0:
            raise ValueError("tolerance_days no puede ser negativo")
        earliest = target - timedelta(days=tolerance_days)
        best: tuple[date, Decimal] | None = None
        for day, value in self.observations:
            if day > target:
                break
            if day >= earliest:
                best = (day, value)
        return best
