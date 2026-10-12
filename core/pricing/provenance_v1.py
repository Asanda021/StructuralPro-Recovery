"""P201-P210 production pricing provenance and auditable application.

This layer composes existing pricing primitives without embedding official
market prices. A price application is accepted only when its source evidence
is verified and its dataset row is valid.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Iterable
import hashlib, json, math

@dataclass(frozen=True)
class PriceApplication:
    item_code: str
    quantity: float
    unit_price: float
    source_id: str
    source_checksum: str
    dataset_year: int
    currency: str = ""
    factors: tuple[float,...] = ()

    def validate(self) -> "PriceApplication":
        if not self.item_code.strip() or not self.source_id.strip() or not self.source_checksum.strip():
            raise ValueError("item_code, source_id and source_checksum are required")
        q=float(self.quantity); p=float(self.unit_price)
        if not math.isfinite(q) or q < 0: raise ValueError("quantity must be finite and non-negative")
        if not math.isfinite(p) or p < 0: raise ValueError("unit_price must be finite and non-negative")
        y=int(self.dataset_year)
        if y < 1300: raise ValueError("invalid dataset year")
        fs=tuple(float(x) for x in self.factors)
        if any(not math.isfinite(x) or x < 0 for x in fs): raise ValueError("invalid factor")
        return self

class PricingProvenance:
    def __init__(self, verified_sources: Iterable[dict[str,Any]]=()):
        self._sources={str(x["source_id"]):dict(x) for x in verified_sources if x.get("source_id")}

    def register_verified_source(self, *, source_id:str, checksum:str, year:int,
                                 license_status:str, publisher:str=""):
        if not source_id.strip() or not checksum.strip(): raise ValueError("source identity/checksum required")
        if license_status not in {"verified","licensed","public"}:
            raise ValueError("source must have an acceptable license status")
        self._sources[source_id]={"source_id":source_id,"checksum":checksum,
            "year":int(year),"license_status":license_status,"publisher":publisher}

    def source(self, source_id:str): return self._sources.get(source_id)

    def apply(self, application:PriceApplication)->dict[str,Any]:
        a=application.validate()
        src=self.source(a.source_id)
        if not src: raise ValueError("price source is not registered")
        if str(src.get("checksum")) != a.source_checksum: raise ValueError("price source checksum mismatch")
        if int(src.get("year")) != a.dataset_year: raise ValueError("price dataset year mismatch")
        factor=1.0
        for f in a.factors: factor*=f
        amount=round(a.quantity*a.unit_price*factor,10)
        evidence={"source_id":a.source_id,"checksum":a.source_checksum,
                  "dataset_year":a.dataset_year,"license_status":src["license_status"],
                  "publisher":src.get("publisher","")}
        return {"item_code":a.item_code,"quantity":a.quantity,"unit_price":a.unit_price,
                "factor":factor,"amount":amount,"evidence":evidence}

    @staticmethod
    def fingerprint(record:dict[str,Any])->str:
        raw=json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        return hashlib.sha256(raw).hexdigest()

def validate_price_application(row:dict[str,Any])->list[str]:
    required=("item_code","quantity","unit_price","source_id","source_checksum","dataset_year")
    return [k for k in required if not str(row.get(k,"")).strip()]
