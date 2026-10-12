"""P381-P390 Universal Multi-Discipline Takeoff Workbench.
A discipline-agnostic deterministic boundary for building/AEC quantity takeoff.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from typing import Mapping, Sequence

ALLOWED_DISCIPLINES = frozenset({"structural","architectural","mechanical","electrical","site"})
ALLOWED_STATUSES = frozenset({"draft","review","accepted","rejected"})
ALLOWED_ACTIONS = frozenset({"add","edit","remove","accept","reject"})

@dataclass(frozen=True)
class TakeoffItem:
    item_id: str
    discipline: str
    category: str
    element_type: str
    source_ids: tuple[str, ...]
    quantity: float | None
    unit: str
    formula: str
    confidence: float
    status: str = "draft"
    revision: str = "A"
    def validate(self):
        if not self.item_id.strip() or not self.category.strip() or not self.element_type.strip(): raise ValueError("item identity is required")
        if self.discipline not in ALLOWED_DISCIPLINES: raise ValueError("unsupported discipline")
        if not self.source_ids: raise ValueError("source identity is required")
        if not 0 <= self.confidence <= 1: raise ValueError("confidence must be between 0 and 1")
        if self.quantity is not None and (not isinstance(self.quantity,(int,float)) or not isfinite(float(self.quantity)) or self.quantity < 0): raise ValueError("quantity must be finite and non-negative")
        if not self.unit.strip(): raise ValueError("unit is required")
        if self.status not in ALLOWED_STATUSES: raise ValueError("invalid status")
        if not self.revision.strip(): raise ValueError("revision is required")
        return self

@dataclass(frozen=True)
class WorkbenchAction:
    action: str
    item_id: str
    before_fingerprint: str
    after_fingerprint: str
    reason: str = ""
    def validate(self):
        if self.action not in ALLOWED_ACTIONS: raise ValueError("invalid workbench action")
        if not self.item_id.strip() or not self.before_fingerprint or not self.after_fingerprint: raise ValueError("action evidence is incomplete")
        return self

class UniversalTakeoffWorkbench:
    def __init__(self, *, minimum_accept_confidence: float = 0.80):
        if not 0 <= minimum_accept_confidence <= 1: raise ValueError("invalid acceptance threshold")
        self.minimum_accept_confidence = minimum_accept_confidence

    @staticmethod
    def _canonical(items: Sequence[TakeoffItem]) -> str:
        payload=[{"item_id":x.item_id,"discipline":x.discipline,"category":x.category,"element_type":x.element_type,
                  "source_ids":list(x.source_ids),"quantity":x.quantity,"unit":x.unit,"formula":x.formula,
                  "confidence":x.confidence,"status":x.status,"revision":x.revision}
                 for x in sorted(items,key=lambda z:z.item_id)]
        return json.dumps(payload,ensure_ascii=False,separators=(",",":"),sort_keys=True)

    @classmethod
    def fingerprint(cls, items: Sequence[TakeoffItem]) -> str:
        return sha256(cls._canonical([x.validate() for x in items]).encode()).hexdigest()

    def accept(self, item: TakeoffItem) -> TakeoffItem:
        item.validate()
        if item.confidence < self.minimum_accept_confidence: raise ValueError("low-confidence takeoff cannot be accepted")
        if item.quantity is None: raise ValueError("quantity is required before acceptance")
        return TakeoffItem(**{**item.__dict__,"status":"accepted"})

    def apply(self, items: Sequence[TakeoffItem], action: WorkbenchAction, replacement: TakeoffItem | None = None):
        action.validate()
        current=tuple(sorted((x.validate() for x in items),key=lambda z:z.item_id))
        if self.fingerprint(current)!=action.before_fingerprint: raise ValueError("action is based on a stale workbench fingerprint")
        by_id={x.item_id:x for x in current}
        if action.action in {"add","edit"}:
            if replacement is None: raise ValueError("replacement item is required")
            replacement.validate()
            if action.action=="add" and replacement.item_id in by_id: raise ValueError("item already exists")
            if action.action=="edit" and replacement.item_id not in by_id: raise ValueError("item to edit does not exist")
            by_id[replacement.item_id]=replacement
        elif action.action=="remove":
            if action.item_id not in by_id: raise ValueError("item to remove does not exist")
            del by_id[action.item_id]
        else:
            if action.item_id not in by_id: raise ValueError("item does not exist")
            old=by_id[action.item_id]
            by_id[action.item_id]=self.accept(old) if action.action=="accept" else TakeoffItem(**{**old.__dict__,"status":"rejected"})
        result=tuple(sorted(by_id.values(),key=lambda z:z.item_id))
        expected= self.fingerprint(result) if result else sha256(b"[]").hexdigest()
        if expected!=action.after_fingerprint: raise ValueError("action after-fingerprint does not match resulting state")
        return result

    def summarize(self, items: Sequence[TakeoffItem]) -> tuple[Mapping[str,object],...]:
        groups={}
        for x in items:
            x.validate(); groups.setdefault((x.discipline,x.unit),[]).append(x)
        return tuple({"discipline":d,"unit":u,"accepted_quantity":sum(float(x.quantity or 0) for x in g if x.status=="accepted"),
                      "accepted_items":sum(x.status=="accepted" for x in g)}
                     for (d,u),g in sorted(groups.items()))
