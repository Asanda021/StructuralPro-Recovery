"""Local, deterministic auto-takeoff assistant.

It is intentionally review-first. No network call and no silent quantity changes.
It combines layer/block/text signals and returns explainable candidates.
"""
from __future__ import annotations
from collections import Counter
from typing import Any

KEYWORDS={
    "wall":["wall","دیوار","walls"],
    "door":["door","در","doors"],
    "window":["window","پنجره","windows"],
    "column":["column","ستون","col"],
    "beam":["beam","تیر"],
    "slab":["slab","دال","سقف"],
    "footing":["footing","پی","foundation"],
}

class LocalAutoTakeoff:
    def classify(self,text:str)->str:
        q=(text or "").casefold()
        for kind,words in KEYWORDS.items():
            if any(w.casefold() in q for w in words): return kind
        return "unknown"

    def auto_scale(self,text:str):
        from core.drawings.graphical_takeoff import extract_scale_candidates
        values=extract_scale_candidates(text)
        return values[0] if values else None

    def auto_count(self,entities):
        groups=Counter()
        for e in entities:
            d=getattr(e,"data",{}) or {}
            key=d.get("block") or getattr(e,"layer","") or getattr(e,"entity_type","")
            if key: groups[str(key)]+=1
        return [{"symbol":k,"count":v,"confidence":0.98} for k,v in groups.items()]

    def auto_takeoff(self,entities):
        out=[]
        for e in entities:
            data=getattr(e,"data",{}) or {}
            text=" ".join(str(data.get(k,"")) for k in ("text","block"))+" "+str(getattr(e,"layer",""))
            kind=self.classify(text)
            if kind=="unknown": continue
            metric="length" if data.get("length") is not None else ("area" if data.get("area") is not None else "count")
            quantity=float(data.get(metric,1))
            unit={"length":"m","area":"m2","count":"عدد"}[metric]
            out.append({"kind":kind,"metric":metric,"quantity":quantity,"unit":unit,
                        "source":f"auto:{getattr(e,'layer','')}",
                        "confidence":0.75,"needs_confirmation":True})
        return out

