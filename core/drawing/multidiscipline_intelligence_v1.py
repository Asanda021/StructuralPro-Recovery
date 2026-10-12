"""P391-P400 deterministic multi-discipline drawing intelligence.
Only explicit evidence is promoted; ambiguous matches remain review-only.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping, Sequence

DISCIPLINES=("structural","architectural","mechanical","electrical","site")
STATUS=("accepted","review","rejected")

@dataclass(frozen=True)
class Classification:
    source_id:str
    discipline:str
    category:str
    element_type:str
    confidence:float
    evidence:tuple[str,...]
    status:str
    def validate(self):
        if not self.source_id.strip(): raise ValueError("source identity is required")
        if self.discipline not in DISCIPLINES: raise ValueError("invalid discipline")
        if not self.category.strip() or not self.element_type.strip(): raise ValueError("classification identity is required")
        if not 0 <= self.confidence <= 1: raise ValueError("invalid confidence")
        if self.status not in STATUS: raise ValueError("invalid status")
        if self.status=="accepted" and self.confidence < .80: raise ValueError("accepted classification requires confidence")
        if self.status=="accepted" and not self.evidence: raise ValueError("accepted classification requires evidence")
        return self

class MultiDisciplineDrawingIntelligence:
    """Maps explicit drawing metadata into a common classification contract."""

    def classify(self, source_id:str, *, discipline:str|None=None, category:str|None=None,
                 element_type:str|None=None, evidence:Sequence[str]=(), confidence:float=0.0)->Classification:
        ev=tuple(sorted({str(x).strip() for x in evidence if str(x).strip()}))
        if not discipline or not category or not element_type:
            return Classification(source_id,discipline or "structural",category or "unknown",
                                  element_type or "unknown",confidence,ev,"rejected").validate()
        status="accepted" if confidence >= .80 and ev else "review"
        return Classification(source_id,discipline,category,element_type,confidence,ev,status).validate()

    @staticmethod
    def fingerprint(rows:Sequence[Classification])->str:
        payload=[{"source_id":x.source_id,"discipline":x.discipline,"category":x.category,
                  "element_type":x.element_type,"confidence":x.confidence,
                  "evidence":list(x.evidence),"status":x.status}
                 for x in sorted((r.validate() for r in rows),key=lambda z:(z.source_id,z.discipline,z.category,z.element_type))]
        return sha256(json.dumps(payload,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode()).hexdigest()

    @staticmethod
    def reconcile(old:Sequence[Classification],new:Sequence[Classification]):
        a={x.source_id:x for x in old}; b={x.source_id:x for x in new}; out=[]
        for sid in sorted(set(a)|set(b)):
            x,y=a.get(sid),b.get(sid)
            if x is None: out.append((sid,"added")); continue
            if y is None: out.append((sid,"removed")); continue
            fields=[]
            for f in ("discipline","category","element_type","confidence","evidence","status"):
                if getattr(x,f)!=getattr(y,f): fields.append(f)
            out.append((sid,"changed" if fields else "unchanged",tuple(fields)))
        return tuple(out)
