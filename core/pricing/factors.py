"""Year-aware commercial factor sets with strict numeric validation and auditability."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from decimal import Decimal, InvalidOperation
import math
from typing import Iterable, Mapping


@dataclass(frozen=True)
class FactorSet:
    year: int
    name: str
    factors: dict[str, float]
    source: str = ""
    effective_date: str = ""
    notes: str = ""


class FactorRegistry:
    """Store explicit factor sets without accepting NaN, infinity, or mutable aliases."""

    def __init__(self, sets: Iterable[FactorSet] = ()):
        self._sets: dict[tuple[int, str], FactorSet] = {}
        for factor_set in sets:
            self.add(factor_set)

    @staticmethod
    def _normalize(factor_set: FactorSet) -> FactorSet:
        if not isinstance(factor_set, FactorSet):
            raise TypeError("factor set must be a FactorSet")
        try:
            raw_year = Decimal(str(factor_set.year))
            if not raw_year.is_finite() or raw_year != raw_year.to_integral_value():
                raise ValueError("invalid year")
            year = int(raw_year)
        except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid year") from exc
        if isinstance(factor_set.year, bool) or year < 1300:
            raise ValueError("invalid year")

        name = factor_set.name.strip() if isinstance(factor_set.name, str) else ""
        if not name:
            raise ValueError("factor set name is required")
        if not isinstance(factor_set.factors, Mapping):
            raise ValueError("factors must be a mapping")

        normalized: dict[str, float] = {}
        for raw_name, raw_rate in factor_set.factors.items():
            key = raw_name.strip() if isinstance(raw_name, str) else ""
            if not key:
                raise ValueError("factor name cannot be empty")
            try:
                rate = float(raw_rate)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"factor rate is invalid: {key}") from exc
            if not math.isfinite(rate) or rate < -1:
                raise ValueError(f"factor rate must be finite and >= -1: {key}")
            if key in normalized:
                raise ValueError(f"duplicate factor name after normalization: {key}")
            normalized[key] = rate

        for field_name in ("source", "effective_date", "notes"):
            if not isinstance(getattr(factor_set, field_name), str):
                raise ValueError(f"{field_name} must be text")

        return FactorSet(
            year=year,
            name=name,
            factors=normalized,
            source=factor_set.source.strip(),
            effective_date=factor_set.effective_date.strip(),
            notes=factor_set.notes.strip(),
        )

    def add(self, factor_set: FactorSet) -> None:
        item = self._normalize(factor_set)
        self._sets[(item.year, item.name)] = item

    def years(self) -> list[int]:
        return sorted({year for year, _ in self._sets}, reverse=True)

    def names(self, year: int) -> list[str]:
        return sorted(name for y, name in self._sets if y == int(year))

    def get(self, year: int, name: str) -> FactorSet | None:
        item = self._sets.get((int(year), name.strip()))
        return None if item is None else replace(item, factors=dict(item.factors))

    def rates(self, year: int, name: str) -> dict[str, float]:
        item = self.get(year, name)
        if item is None:
            raise KeyError((year, name))
        return dict(item.factors)

    def describe(self, year: int, name: str) -> dict[str, object] | None:
        item = self.get(year, name)
        return None if item is None else asdict(item)
