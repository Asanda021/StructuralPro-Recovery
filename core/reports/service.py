"""Unified reporting service for takeoff, BOQ, estimate, revision and audit outputs."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable
import math
from .project_report import ProjectReport
from .designer import ReportLayout
from .rtl import report_schema

REPORT_TYPES={"takeoff","boq","estimate","financial","revision","drawing","audit"}

def _rows(rows): return [dict(r) for r in rows]
def _finite(v,n):
    try: x=float(v)
    except (TypeError,ValueError) as e: raise ValueError(f"{n} must be numeric") from e
    if not math.isfinite(x): raise ValueError(f"{n} must be finite")
    return x

@dataclass(frozen=True)
class ReportRequest:
    report_type:str
    title:str
    language:str="fa"
    rtl:bool=True
    decimals:int=2
    currency:str="IRR"
    group_by:str=""
    page_size:int=35
    include_cancelled:bool=False
    filters:dict[str,Any]=field(default_factory=dict)
    def __post_init__(self):
        if self.report_type not in REPORT_TYPES: raise ValueError(f"unsupported report type: {self.report_type}")
        if not str(self.title).strip(): raise ValueError("title is required")
        if self.decimals<0 or self.decimals>8: raise ValueError("decimals must be between 0 and 8")
        if self.page_size<=0: raise ValueError("page_size must be positive")

class ReportService:
    """Builds deterministic report payloads without mutating source rows."""
    @staticmethod
    def filter_rows(rows:Iterable[dict[str,Any]], request:ReportRequest)->list[dict[str,Any]]:
        out=[]
        for row in _rows(rows):
            if not request.include_cancelled and str(row.get("status","active")).lower()=="cancelled": continue
            ok=True
            for key,wanted in request.filters.items():
                if wanted is None or wanted=="": continue
                value=row.get(key)
                if isinstance(wanted,(list,tuple,set)): ok=value in wanted
                else: ok=str(value)==str(wanted)
                if not ok: break
            if ok: out.append(row)
        return out

    @staticmethod
    def build(request:ReportRequest, rows:Iterable[dict[str,Any]], *, summary=None, metadata=None)->dict[str,Any]:
        selected=ReportService.filter_rows(rows,request)
        layout=ReportLayout(title=request.title,group_by=request.group_by,rtl=request.rtl,page_size=request.page_size)
        pages=layout.pages(selected)
        report=ProjectReport(request.title,selected,summary or {},metadata or {})
        validation=report.validate()
        schema=report_schema([label for _,label in report.columns()],request.language,request.rtl,request.decimals,request.currency)
        amounts=[_finite(r.get("total",0) or 0,"total") for r in selected]
        return {"type":request.report_type,"title":request.title,"language":request.language,"rtl":request.rtl,
                "schema":schema,"columns":report.columns(),"rows":report.as_rows(),"pages":pages,
                "summary":dict(summary or {}),"metadata":dict(metadata or {}),"validation":validation,
                "totals":{"line_count":len(selected),"amount":sum(amounts)}}

    @staticmethod
    def build_audit(request:ReportRequest, *, events:Iterable[dict[str,Any]])->dict[str,Any]:
        rows=[]
        for i,event in enumerate(events,1):
            e=dict(event); e.setdefault("item_no",i); e.setdefault("description",str(e.get("action") or e.get("event") or "audit event")); rows.append(e)
        return ReportService.build(request,rows,metadata={"audit":True})
