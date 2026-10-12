"""P401-P410 deterministic universal building takeoff orchestration.
It aggregates already-evidenced quantities; it does not infer missing dimensions.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from typing import Sequence

@dataclass(frozen=True)
class TakeoffRecord:
    record_id:str
    discipline:str
    category:str
    source_ids:tuple[str,...]
    quantity:float
    unit:str
    formula:str
    revision:str
    status:str="accepted"
    def validate(self):
        if not self.record_id.strip() or not self.discipline.strip() or not self.category.strip(): raise ValueError("identity is required")
        if not self.source_ids: raise ValueError("source identity is required")
        if not isinstance(self.quantity,(int,float)) or not isfinite(float(self.quantity)) or self.quantity<0: raise ValueError("quantity must be finite and non-negative")
        if not self.unit.strip() or not self.formula.strip() or not self.revision.strip(): raise ValueError("quantity evidence is incomplete")
        if self.status!="accepted": raise ValueError("only accepted records can enter production aggregation")
        return self

class UniversalBuildingTakeoff:
    @staticmethod
    def fingerprint(records:Sequence[TakeoffRecord])->str:
        payload=[r.__dict__ for r in sorted((x.validate() for x in records),key=lambda z:z.record_id)]
        return sha256(json.dumps(payload,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode()).hexdigest()

    def aggregate(self, records:Sequence[TakeoffRecord]):
        groups={}
        for r in records:
            r.validate()
            key=(r.discipline,r.category,r.unit)
            groups.setdefault(key,[]).append(r)
        return tuple({"discipline":d,"category":c,"unit":u,
                      "quantity":sum(float(x.quantity) for x in rows),
                      "record_ids":tuple(x.record_id for x in rows),
                      "source_ids":tuple(sorted({s for x in rows for s in x.source_ids}))}
                     for (d,c,u),rows in sorted(groups.items()))

    def revision_delta(self, before:Sequence[TakeoffRecord], after:Sequence[TakeoffRecord]):
        a={x.record_id:x for x in before}; b={x.record_id:x for x in after}; out=[]
        for rid in sorted(set(a)|set(b)):
            if rid not in a: out.append((rid,"added"))
            elif rid not in b: out.append((rid,"removed"))
            elif a[rid]!=b[rid]: out.append((rid,"changed"))
            else: out.append((rid,"unchanged"))
        return tuple(out)
