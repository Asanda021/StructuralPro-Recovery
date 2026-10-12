"""Unified offline-first quantity takeoff engine.

Stage 1: one normalized interface for all current construction domains.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Iterable
import math
from .modules import calculate_building_item, calculate_mechanical_item, calculate_electrical_item, calculate_civil_item
from .modules.advanced import calculate_advanced_item
from .units import normalize_unit

@dataclass(frozen=True)
class TakeoffRow:
    domain: str
    item: str
    description: str
    quantity: float
    unit: str
    formula: str
    source: str = "manual"
    price_code: str | None = None
    warning: str = ""
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class TakeoffEngine:
    DOMAINS = ("building","mechanical","electrical","civil","advanced")
    def calculate(self, domain: str, item: str, *, description: str = "", source: str = "manual",
                  price_code: str | None = None, **params: Any) -> TakeoffRow:
        d=domain.strip().casefold()
        if d=="building": result=calculate_building_item(item,**params)
        elif d=="mechanical": result=calculate_mechanical_item(item,**params)
        elif d=="electrical": result=calculate_electrical_item(item,**params)
        elif d=="civil": result=calculate_civil_item(item,**params)
        elif d=="advanced": result=calculate_advanced_item(item,**params)
        else: raise KeyError(f"unsupported takeoff domain: {domain}")
        if not math.isfinite(float(result.quantity)) or result.quantity < 0:
            raise ValueError("نتیجه متره باید متناهی و نامنفی باشد")
        return TakeoffRow(d,item,description or item,float(result.quantity),result.unit,result.formula,
                          source,price_code,";".join(getattr(result,"warnings",()) or ()))
    def batch(self, rows: Iterable[dict[str,Any]]) -> list[TakeoffRow]:
        out=[]
        for row in rows:
            data=dict(row); domain=data.pop("domain"); item=data.pop("item")
            out.append(self.calculate(domain,item,description=data.pop("description",""),
                                      source=data.pop("source","manual"),
                                      price_code=data.pop("price_code",None),**data))
        return out
    @staticmethod
    def summarize(rows: Iterable[TakeoffRow]) -> dict[str,Any]:
        """Summarize only compatible quantities; do not add m, m2, kg or counts.

        The historic flat quantity_by_domain remains numeric for domains with
        exactly one canonical unit. Mixed-unit domains become None (review
        required), with all real values retained in quantity_by_domain_unit.
        """
        rows=list(rows); by_unit={}; by_domain_unit={}
        for row in rows:
            if isinstance(row.quantity, bool):
                raise ValueError("مقدار متره نباید بولی باشد")
            try:
                quantity=float(row.quantity)
            except (TypeError,ValueError,OverflowError) as exc:
                raise ValueError("مقدار متره باید عدد معتبر باشد") from exc
            if not math.isfinite(quantity) or quantity<0:
                raise ValueError("مقدار متره باید متناهی و نامنفی باشد")
            unit=normalize_unit(row.unit)
            domain=str(row.domain).strip()
            if not domain:
                raise ValueError("حوزه متره باید مشخص باشد")
            next_total=by_unit.get(unit,0.0)+quantity
            if not math.isfinite(next_total):
                raise ValueError("جمع واحد متره موجب سرریز عددی شد")
            bucket=by_domain_unit.setdefault(domain,{})
            next_domain=bucket.get(unit,0.0)+quantity
            if not math.isfinite(next_domain):
                raise ValueError("جمع متره در حوزه و واحد موجب سرریز عددی شد")
            by_unit[unit]=next_total
            bucket[unit]=next_domain
        by_domain={domain: next(iter(units.values())) if len(units)==1 else None
                   for domain,units in by_domain_unit.items()}
        mixed=sorted(domain for domain,units in by_domain_unit.items() if len(units)>1)
        return {"row_count":len(rows),"quantity_by_unit":by_unit,"quantity_by_domain":by_domain,
                "quantity_by_domain_unit":by_domain_unit,"mixed_unit_domains":mixed,
                "warnings":[r.to_dict() for r in rows if r.warning]}
