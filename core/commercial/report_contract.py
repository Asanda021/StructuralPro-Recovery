"""Stable RTL/report data contract independent of rendering engine."""
from dataclasses import dataclass
from datetime import datetime,timezone

@dataclass(frozen=True)
class ReportMeta:
    title:str; project:str; language:str="fa-IR"; direction:str="rtl"; generated_at:str=""

def build_report(title,project,sections):
    meta=ReportMeta(title,project,generated_at=datetime.now(timezone.utc).isoformat())
    return {"meta":meta.__dict__,"sections":[{"title":str(k),"rows":list(v)} for k,v in sections.items()]}
