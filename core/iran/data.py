"""Iran construction data registry.

Keeps Iranian price-list metadata, source provenance, annual datasets and
adjustment-index imports separate from the calculation engine. No official
price or index value is fabricated in source code.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from io import StringIO
import csv
import math
from typing import Any, Iterable


@dataclass(frozen=True)
class IranDatasetSource:
    year: int
    discipline: str
    title: str
    publisher: str
    circular_number: str = ""
    circular_date: str = ""
    source_url: str = ""
    verified: bool = False
    notes: str = ""


@dataclass(frozen=True)
class AdjustmentIndex:
    year: int
    quarter: int
    discipline: str
    index: float
    source_id: str
    source_url: str = ""
    provisional: bool = False

    def __post_init__(self) -> None:
        if self.year < 1300 or not 1 <= int(self.quarter) <= 4:
            raise ValueError("invalid adjustment-index period")
        if not math.isfinite(float(self.index)) or float(self.index) < 0:
            raise ValueError("adjustment index must be finite and non-negative")
        if not str(self.discipline).strip() or not str(self.source_id).strip():
            raise ValueError("discipline and source_id are required")


class IranDataRegistry:
    def __init__(self) -> None:
        self._sources: dict[tuple[int, str], IranDatasetSource] = {}
        self._indices: dict[tuple[int, int, str], AdjustmentIndex] = {}

    def register_source(self, source: IranDatasetSource) -> None:
        if source.year < 1300 or not source.discipline.strip() or not source.publisher.strip():
            raise ValueError("invalid Iranian dataset source")
        self._sources[(source.year, source.discipline.strip())] = source

    def source(self, year: int, discipline: str) -> IranDatasetSource | None:
        return self._sources.get((int(year), discipline.strip()))

    def sources(self, year: int | None = None, *, verified_only: bool = False) -> list[dict[str, Any]]:
        rows = []
        for x in self._sources.values():
            if year is not None and x.year != int(year):
                continue
            if verified_only and not x.verified:
                continue
            rows.append(asdict(x))
        return sorted(rows, key=lambda x: (x["year"], x["discipline"]), reverse=True)

    def add_adjustment_index(self, item: AdjustmentIndex) -> None:
        self._indices[(item.year, item.quarter, item.discipline.strip())] = item

    def adjustment_index(self, year: int, quarter: int, discipline: str) -> AdjustmentIndex | None:
        return self._indices.get((int(year), int(quarter), discipline.strip()))

    def adjustment_indices(self, year: int | None = None) -> list[dict[str, Any]]:
        rows = [asdict(x) for x in self._indices.values() if year is None or x.year == int(year)]
        return sorted(rows, key=lambda x: (x["year"], x["quarter"], x["discipline"]), reverse=True)

    def apply_adjustment(self, base_amount: float, *, year: int, quarter: int,
                         discipline: str) -> dict[str, Any]:
        amount = float(base_amount)
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("base amount must be finite and non-negative")
        item = self.adjustment_index(year, quarter, discipline)
        if item is None:
            return {"status": "missing_index", "base_amount": amount}
        adjusted = amount * item.index
        return {
            "status": "ok",
            "base_amount": amount,
            "index": item.index,
            "adjusted_amount": adjusted,
            "source_id": item.source_id,
            "provisional": item.provisional,
        }

    @staticmethod
    def fingerprint(text: str) -> str:
        return sha256(text.encode("utf-8")).hexdigest()

    def import_adjustment_csv(self, text: str, *, source_id: str,
                              source_url: str = "", provisional: bool = False) -> dict[str, Any]:
        reader = csv.DictReader(StringIO(text))
        required = {"year", "quarter", "discipline", "index"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("adjustment CSV requires year,quarter,discipline,index")
        rows = list(reader)
        for n, row in enumerate(rows, 2):
            try:
                item = AdjustmentIndex(
                    int(row["year"]), int(row["quarter"]), str(row["discipline"]).strip(),
                    float(row["index"]), source_id, source_url, provisional,
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid adjustment row {n}: {exc}") from exc
            self.add_adjustment_index(item)
        return {
            "rows": len(rows),
            "source_id": source_id,
            "sha256": self.fingerprint(text),
            "provisional": provisional,
        }


def default_iran_sources() -> list[IranDatasetSource]:
    """Known source metadata only; actual price rows must be imported."""
    return [
        IranDatasetSource(
            year=1404,
            discipline="ابنیه",
            title="فهرست بهای واحد پایه رشته ابنیه سال ۱۴۰۴",
            publisher="سازمان برنامه و بودجه کشور",
            circular_number="۱۴۰۳/۷۷۴۹۴۸",
            circular_date="۱۴۰۳/۱۲/۲۹",
            source_url="https://sama.mporg.ir/sites/publish/SitePages/ZabetehView.aspx?mdid=5957",
            verified=True,
            notes="نسخه مرجع برای داده‌های قیمت؛ ردیف‌ها باید از سند رسمی/فایل کنترل‌شده وارد شوند.",
        )
    ]
