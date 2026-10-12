"""Annual price-list registry and validation.

Stage 2: official/verified datasets are imported as data packages.  The
software does not fabricate prices.  Dataset provenance is stored beside the
rows so users can distinguish official, imported and custom catalogs.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Any

@dataclass(frozen=True)
class DatasetInfo:
    year: int
    discipline: str
    title: str
    source: str
    verified: bool = False
    version: str = ""

class PriceDatasetRegistry:
    def __init__(self):
        self._datasets: dict[tuple[int, str], DatasetInfo] = {}

    def register(self, info: DatasetInfo) -> None:
        if info.year < 1300:
            raise ValueError("invalid Persian price-list year")
        if not info.discipline.strip():
            raise ValueError("discipline is required")
        if not info.source.strip():
            raise ValueError("source is required")
        self._datasets[(info.year, info.discipline.strip())] = info

    def get(self, year: int, discipline: str) -> DatasetInfo | None:
        return self._datasets.get((int(year), discipline.strip()))

    def years(self) -> list[int]:
        return sorted({y for y, _ in self._datasets}, reverse=True)

    def disciplines(self, year: int | None = None) -> list[str]:
        return sorted({d for (y, d) in self._datasets if year is None or y == int(year)})

    def verified(self, year: int | None = None) -> list[DatasetInfo]:
        return [x for x in self._datasets.values()
                if x.verified and (year is None or x.year == int(year))]

    def manifest(self) -> list[dict[str, Any]]:
        return [
            {"year": x.year, "discipline": x.discipline, "title": x.title,
             "source": x.source, "verified": x.verified, "version": x.version}
            for x in sorted(self._datasets.values(), key=lambda z: (z.year, z.discipline), reverse=True)
        ]
