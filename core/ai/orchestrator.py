"""Unified, review-first AI orchestration for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .project_assistant import ProjectAssistant
from .auto_takeoff import LocalAutoTakeoff
from .takeoff_assistant import LocalTakeoffAssistant
@dataclass(frozen=True)
class AISuggestion:
    kind:str; payload:dict[str,Any]; confidence:float; requires_confirmation:bool=True; source_ids:tuple[str,...]=()
    def __post_init__(self):
        if not 0<=self.confidence<=1: raise ValueError("confidence must be between 0 and 1")
class AIOrchestrator:
    def __init__(self): self.project=ProjectAssistant(); self.takeoff=LocalTakeoffAssistant(); self.auto=LocalAutoTakeoff()
    def understand_drawing(self,entities):
        out=[]
        for e in entities:
            data=getattr(e,"data",{}) or {}; layer=str(getattr(e,"layer","") or data.get("layer","")); text=" ".join(str(data.get(k,"")) for k in ("text","block","entity_type")); kind=self.auto.classify(layer+" "+text)
            if kind=="unknown": continue
            sid=str(data.get("source_id") or getattr(e,"source_id","") or layer); out.append(AISuggestion("drawing_element",{"kind":kind,"layer":layer,"text":text},0.75,True,(sid,)))
        return out
    def suggest_takeoff(self,entities): return [AISuggestion("takeoff",x,float(x.get("confidence",0)),True,(str(x.get("source","")),)) for x in self.auto.auto_takeoff(entities)]
    def suggest_boq_mapping(self,entities,catalog): return [AISuggestion("boq_mapping",x,0.5,True,(str(x.get("entity",{}).get("source_id", "")),)) for x in self.takeoff.suggest_mapping(entities,catalog) if x.get("suggestions")]
    def analyze_revision(self,old,new): return [AISuggestion("revision",x,1.0,True,(str(x.get("key","")),)) for x in self.project.compare_rows(old,new)]
    def qa(self,rows): return self.takeoff.qa(rows)
    def query(self,question,context):
        q=str(question or "").strip()
        if not q: raise ValueError("question is required")
        if not isinstance(context,dict): raise ValueError("context must be a mapping")
        ql=q.casefold(); rows=list(context.get("rows",[]))
        if any(k in ql for k in ("جمع","total","مبلغ")):
            import math
            total=0.0
            for row in rows:
                try: value=float(row.get("total",0) or 0)
                except (TypeError,ValueError) as exc: raise ValueError("row total must be numeric") from exc
                if not math.isfinite(value): raise ValueError("row total must be finite")
                total += value
            return {"answer":total,"unit":context.get("currency","IRR"),"source":"context.rows"}
        if any(k in ql for k in ("تعداد","count")): return {"answer":len(rows),"unit":"rows","source":"context.rows"}
        return {"answer":None,"supported":False,"reason":"unsupported_query","requires_source_data":True}
