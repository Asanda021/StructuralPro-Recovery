"""P44 — evidence-first professional reporting.

Produces deterministic structured report data for BOQ/takeoff/revision/estimate
and management views. Rendering is intentionally separated from source data.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from typing import Iterable

@dataclass(frozen=True)
class ReportRow:
    item_code: str
    description: str
    unit: str
    quantity: Decimal
    source_id: str
    amount: Decimal | None = None
    currency: str | None = None
    change: Decimal | None = None

@dataclass(frozen=True)
class ProfessionalReport:
    report_type: str
    title: str
    project_id: str
    rows: tuple[dict[str, object], ...]
    totals: dict[str, Decimal]
    branding: dict[str, str]
    fingerprint: str

def build_report(rows: Iterable[ReportRow], *, report_type: str, title: str,
                 project_id: str, branding: dict[str, str] | None = None) -> ProfessionalReport:
    for value in (report_type, title, project_id):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("report identity is incomplete")
    normalized = dict(branding or {})
    if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) for k, v in normalized.items()):
        raise ValueError("branding must contain text key/value pairs")
    seen=set(); out=[]; quantity=Decimal("0"); amount=Decimal("0"); change=Decimal("0")
    for row in rows:
        if not all(isinstance(x, str) and x.strip() for x in (row.item_code,row.description,row.unit,row.source_id)):
            raise ValueError("report row identity is incomplete")
        if row.item_code in seen: raise ValueError(f"duplicate report item: {row.item_code}")
        seen.add(row.item_code)
        if not row.quantity.is_finite() or row.quantity < 0: raise ValueError("invalid report quantity")
        if row.amount is not None and (not row.amount.is_finite() or row.amount < 0): raise ValueError("invalid report amount")
        if row.change is not None and not row.change.is_finite(): raise ValueError("invalid report change")
        if row.amount is not None and row.currency is None: raise ValueError("amount requires currency")
        out.append({"item_code":row.item_code,"description":row.description,"unit":row.unit,"quantity":row.quantity,"source_id":row.source_id,"amount":row.amount,"currency":row.currency,"change":row.change})
        quantity += row.quantity
        if row.amount is not None: amount += row.amount
        if row.change is not None: change += row.change
    totals={"quantity":quantity,"amount":amount,"change":change}
    payload=_normalize({"report_type":report_type,"title":title,"project_id":project_id,"rows":out,"totals":totals,"branding":normalized})
    fp=sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":" )).encode()).hexdigest()
    return ProfessionalReport(report_type,title,project_id,tuple(out),totals,normalized,fp)

def export_schema(report: ProfessionalReport, *, format: str) -> dict[str, object]:
    if format not in {"xlsx","pdf","json"}: raise ValueError("unsupported report format")
    return {"format":format,"report_type":report.report_type,"title":report.title,"project_id":report.project_id,"branding":dict(report.branding),"columns":["item_code","description","unit","quantity","source_id","amount","currency","change"],"rows":list(report.rows),"totals":dict(report.totals),"fingerprint":report.fingerprint}

def _normalize(v):
    if isinstance(v,Decimal): return str(v)
    if isinstance(v,dict): return {str(k):_normalize(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [_normalize(x) for x in v]
    return v
