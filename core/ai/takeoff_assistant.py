"""Local AI-facing contracts for drawing classification and quantity QA.
No network calls are made here.
"""
from __future__ import annotations
from typing import Any
import math

class LocalTakeoffAssistant:
    def suggest_mapping(self, entities:list[dict[str,Any]], catalog:list[dict[str,Any]])->list[dict[str,Any]]:
        out=[]
        for e in entities:
            text=" ".join(str(e.get(k,"")) for k in ("layer","entity_type","text","block_name")).lower()
            matches=[]
            for item in catalog:
                hay=" ".join(str(item.get(k,"")) for k in ("code","description","group","chapter")).lower()
                score=sum(1 for token in text.split() if token and token in hay)
                if score: matches.append((score,item))
            matches.sort(key=lambda x:x[0],reverse=True)
            out.append({"entity":e,"suggestions":[m for _,m in matches[:5]]})
        return out

    def qa(self, rows:list[dict[str,Any]])->list[dict[str,Any]]:
        issues=[]
        for i,r in enumerate(rows,1):
            try:
                if isinstance(r.get("quantity"), bool): raise ValueError("boolean quantity")
                q=float(r.get("quantity"))
                if not math.isfinite(q): raise ValueError("non-finite quantity")
            except (TypeError,ValueError,OverflowError):
                issues.append({"row":i,"severity":"error","code":"invalid_quantity"}); continue
            if q<0: issues.append({"row":i,"severity":"error","code":"negative_quantity"})
            if not str(r.get("unit","")).strip(): issues.append({"row":i,"severity":"warning","code":"missing_unit"})
            if not str(r.get("price_code","")).strip(): issues.append({"row":i,"severity":"warning","code":"missing_price_code"})
        return issues


class SafeTakeoffSuggestion:
    """Presentation boundary: suggestions require explicit human confirmation."""
    def __init__(self, assistant=None): self.assistant=assistant or LocalTakeoffAssistant()
    def explain(self, suggestion): return {"suggestion":suggestion,"requires_user_confirmation":True,"deterministic":False}
