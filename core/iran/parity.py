from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Iterable
import csv
from io import StringIO
import math

from core.iran.boq import concrete_to_boq, member_catalog
from core.pricing.catalog import PriceCatalog

@dataclass(frozen=True)
class IranianCoefficient:
    code: str
    title: str
    value: float = 1.0
    unit: str = ""
    notes: str = ""
    def __post_init__(self):
        if not self.code.strip() or not self.title.strip(): raise ValueError("coefficient code and title are required")
        if not math.isfinite(float(self.value)) or float(self.value) < 0: raise ValueError("coefficient value must be finite and non-negative")

@dataclass(frozen=True)
class PriceBookVersion:
    year: int
    discipline: str
    title: str
    version: str = "official"
    source_id: str = ""
    verified: bool = False
    def __post_init__(self):
        if self.year < 1300 or not self.discipline.strip() or not self.title.strip(): raise ValueError("invalid price-book metadata")

class IranianTakeoffParity:
    def __init__(self, catalog: PriceCatalog | None = None):
        self.catalog = catalog or PriceCatalog()
        self._books = {}
        self._coefficients = {}
    def register_price_book(self, book): self._books[(book.year, book.discipline.strip(), book.version.strip())] = book
    def price_books(self, *, year=None, discipline=None):
        rows=[]
        for book in self._books.values():
            if year is not None and book.year != int(year): continue
            if discipline is not None and book.discipline != discipline.strip(): continue
            rows.append(asdict(book))
        return sorted(rows, key=lambda x:(x['year'],x['discipline'],x['version']), reverse=True)
    def register_coefficient(self, coefficient): self._coefficients[coefficient.code.strip()] = coefficient
    def coefficients(self): return [asdict(x) for x in sorted(self._coefficients.values(), key=lambda x:x.code)]
    def coefficient(self, code): return self._coefficients.get(code.strip())
    def apply_coefficients(self, quantity, codes=()):
        q=float(quantity)
        if not math.isfinite(q) or q<0: raise ValueError('quantity must be finite and non-negative')
        applied=[]; result=q
        for code in codes:
            item=self.coefficient(code)
            if item is None: raise KeyError(code)
            result*=item.value; applied.append(asdict(item))
        result = round(result, 12)
        return {'base_quantity':q,'quantity':result,'coefficients':applied}
    def chapters(self, year, discipline=None): return self.catalog.chapters(year=year, group=discipline)
    def groups(self, year): return self.catalog.groups(year)
    def items(self, year, *, discipline=None, chapter=None, query='', limit=100):
        return [asdict(x) for x in self.catalog.search(query, year=year, group=discipline, chapter=chapter, limit=limit)]
    def import_price_book_csv(self, text, *, replace_year=False, metadata=None):
        count=self.catalog.import_csv(text, replace_year=replace_year)
        if metadata: self.register_price_book(metadata)
        return count
    def export_price_book_csv(self, year=None): return self.catalog.export_csv(year)
    def snapshot(self, year, codes): return {'year':int(year),'items':self.catalog.snapshot(codes,year),'price_book':self.price_books(year=year)}
    def concrete_member_boq(self, member_type, geometry, rebar=()): return concrete_to_boq(member_type, geometry, rebar)
    @staticmethod
    def member_catalog(): return member_catalog()

def build_project_takeoff(*, project_id, project_name, rows, price_year=None, coefficients=()):
    if not project_id.strip() or not project_name.strip(): raise ValueError('project_id and project_name are required')
    output=[]
    for row in rows:
        item=dict(row); q=float(item.get('quantity',0))
        if not math.isfinite(q) or q<0: raise ValueError('row quantity must be finite and non-negative')
        item['coefficient_codes']=list(coefficients); item['price_year']=price_year; output.append(item)
    return {'schema':'structuralpro.iran.takeoff.v1','project_id':project_id.strip(),'project_name':project_name.strip(),'price_year':price_year,'rows':output}

def export_project_csv(rows):
    rows=[dict(x) for x in rows]; fields=['project_id','project_name','item_code','description','unit','quantity','price_year','price_code','unit_price']
    buf=StringIO(); writer=csv.DictWriter(buf,fieldnames=fields,extrasaction='ignore'); writer.writeheader()
    for row in rows: writer.writerow(row)
    return buf.getvalue()
