"""Offline-first price catalog with year/discipline/chapter indexing and snapshots."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Iterable, Any
import csv
from io import StringIO
import math

@dataclass(frozen=True)
class PriceItem:
    year: int
    group: str
    chapter: str
    code: str
    description: str
    unit: str
    unit_price: float
    analysis: str = ""
    notes: str = ""

class PriceCatalog:
    def __init__(self, items: Iterable[PriceItem] = (), source_registry=None):
        self._items: dict[tuple[int,str], PriceItem] = {}
        self._overrides: dict[tuple[int,str], PriceItem] = {}
        self._history: dict[tuple[int,str], list[dict[str, Any]]] = {}
        self.source_registry=source_registry
        self.replace(items)

    def replace(self, items: Iterable[PriceItem]) -> None:
        self._items = {}
        for item in items:
            self.add(item, record_history=False)

    @staticmethod
    def _validate_item(item: PriceItem) -> PriceItem:
        year = int(item.year)
        code = str(item.code).strip()
        unit = str(item.unit).strip()
        price = float(item.unit_price)
        if not code:
            raise ValueError("price code is required")
        if not unit:
            raise ValueError("price unit is required")
        if not math.isfinite(price) or price < 0:
            raise ValueError("unit price must be finite and non-negative")
        return PriceItem(year, str(item.group).strip(), str(item.chapter).strip(),
                         code, str(item.description).strip(), unit, price,
                         str(item.analysis or ""), str(item.notes or ""))

    def _key(self, year: int, code: str) -> tuple[int, str]:
        return int(year), str(code).strip()


    def add(self, item: PriceItem, *, record_history: bool = True) -> None:
        item = self._validate_item(item)
        key = self._key(item.year, item.code)
        old = self._items.get(key)
        self._items[key] = item
        if record_history and old is not None and old.unit_price != item.unit_price:
            self._history.setdefault(key, []).append({
                "year": item.year, "code": item.code,
                "old_price": old.unit_price, "new_price": item.unit_price,
            })

    def set_custom_price(self, code: str, year: int, unit_price: float,
                         *, reason: str = "") -> PriceItem:
        base = self.get(code, year)
        if base is None:
            raise KeyError(code)
        price = float(unit_price)
        if not math.isfinite(price) or price < 0:
            raise ValueError("custom price must be finite and non-negative")
        custom = PriceItem(base.year, base.group, base.chapter, base.code,
                           base.description, base.unit, price, base.analysis,
                           reason or base.notes)
        self._overrides[self._key(year, code)] = custom
        return custom

    def clear_custom_price(self, code: str, year: int) -> None:
        self._overrides.pop(self._key(year, code), None)

    def price_history(self, code: str, year: int) -> list[dict[str, Any]]:
        return list(self._history.get(self._key(year, code), []))

    def years(self) -> list[int]:
        return sorted({k[0] for k in self._items}, reverse=True)

    def groups(self, year: int | None = None) -> list[str]:
        return sorted({x.group for x in self._items.values() if year is None or x.year == year})

    def chapters(self, year: int | None = None, group: str | None = None) -> list[str]:
        return sorted({x.chapter for x in self._items.values()
                       if (year is None or x.year == year) and (group is None or x.group == group)})

    def get(self, code: str, year: int | None = None) -> PriceItem | None:
        code = code.strip()
        if year is not None:
            key = self._key(year, code)
            return self._overrides.get(key) or self._items.get(key)
        matches = [self._overrides.get((y, code)) or x for (y,c), x in self._items.items() if c == code]
        return sorted(matches, key=lambda x: x.year, reverse=True)[0] if matches else None

    def search(self, query: str, year: int | None = None, group: str | None = None,
               chapter: str | None = None, limit: int = 100) -> list[PriceItem]:
        q = query.strip().casefold()
        rows = []
        for x in self._items.values():
            if year is not None and x.year != int(year): continue
            if group is not None and x.group != group: continue
            if chapter is not None and x.chapter != chapter: continue
            hay = " ".join((x.code, x.description, x.unit, x.analysis, x.notes)).casefold()
            if not q or q in hay:
                rows.append(x)
        rows.sort(key=lambda x: (x.year, x.code), reverse=True)
        return rows[:max(1, limit)]

    @staticmethod
    def _units_compatible(a: str, b: str) -> bool:
        aliases = [{"m", "م", "متر"}, {"m2", "m²", "م2", "مترمربع"}, {"m3", "m³", "م3", "مترمکعب"}, {"kg", "کیلو", "کیلوگرم"}, {"عدد", "pcs", "piece", "count"}]
        a, b = str(a).strip().casefold(), str(b).strip().casefold()
        return a == b or any(a in group and b in group for group in aliases)

    def resolve(self, code: str, year: int | None = None, unit: str | None = None) -> dict[str, Any]:
        item = self.get(code, year)
        if item is None: return {"status":"not_found", "code":code}
        if unit and not self._units_compatible(item.unit, unit):
            return {"status":"unit_mismatch", "code":code, "expected_unit":item.unit, "actual_unit":unit}
        if item.unit_price < 0: return {"status":"invalid_price", "code":code}
        if item.unit_price == 0: return {"status":"zero_price", "code":code, "item":item}
        return {"status":"ok", "code":code, "item":item, "unit_price":item.unit_price}

    def source_info(self, year:int, discipline:str="building", source_id:str=""):
        return self.source_registry.get(year,discipline,source_id) if self.source_registry else None

    def snapshot(self, codes: Iterable[str], year: int | None = None) -> list[dict[str, Any]]:
        out=[]
        for code in codes:
            item=self.get(code, year)
            if item is not None:
                out.append(asdict(item))
        return out

    def export_csv(self, year: int | None = None) -> str:
        rows=[x for x in self._items.values() if year is None or x.year == int(year)]
        buf=StringIO()
        fields=["year","group","chapter","code","description","unit","unit_price","analysis","notes"]
        w=csv.DictWriter(buf, fieldnames=fields); w.writeheader()
        for x in sorted(rows,key=lambda z:(z.year,z.code)): w.writerow(asdict(x))
        return buf.getvalue()

    def import_csv(self, text: str, replace_year: bool = False) -> int:
        reader=csv.DictReader(StringIO(text))
        rows=[]
        for raw in reader:
            rows.append(PriceItem(
                year=int(raw["year"]), group=raw["group"].strip(), chapter=raw["chapter"].strip(),
                code=raw["code"].strip(), description=raw["description"].strip(), unit=raw["unit"].strip(),
                unit_price=float(raw["unit_price"]), analysis=raw.get("analysis",""), notes=raw.get("notes","")))
        if replace_year:
            years={x.year for x in rows}
            self._items={k:v for k,v in self._items.items() if k[0] not in years}
        for x in rows: self.add(x)
        return len(rows)
