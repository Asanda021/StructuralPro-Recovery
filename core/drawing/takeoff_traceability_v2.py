"""P161-P170 deterministic takeoff traceability hardening.

Extends the existing source -> element -> quantity lineage without inventing
engineering values. All acceptance decisions remain fail-closed and auditable.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import Mapping, Sequence

@dataclass(frozen=True)
class TraceCoverage:
    source_id: str
    element_ids: tuple[str, ...]
    quantity_ids: tuple[str, ...]
    status: str
    warnings: tuple[str, ...] = ()
    def validate(self):
        if not self.source_id.strip(): raise ValueError("source identity is required")
        if self.status not in {"covered","partial","uncovered","review"}: raise ValueError("invalid coverage status")
        return self

@dataclass(frozen=True)
class NormalizedCandidate:
    element_id: str
    quantity: float | None
    unit: str
    formula: str
    source_ids: tuple[str, ...]
    confidence: float
    status: str
    warnings: tuple[str, ...]
    fingerprint: str
    def validate(self):
        if not self.element_id.strip(): raise ValueError("element identity is required")
        if self.quantity is not None and (not isfinite(float(self.quantity)) or float(self.quantity) < 0):
            raise ValueError("quantity must be finite and non-negative")
        if not 0 <= self.confidence <= 1: raise ValueError("invalid confidence")
        if self.status not in {"accepted","review","rejected"}: raise ValueError("invalid status")
        if self.status == "accepted" and (self.quantity is None or not self.unit or not self.source_ids):
            raise ValueError("accepted candidate must have quantity, unit and source")
        return self

class TakeoffTraceabilityV2:
    """Deterministic normalization, coverage and fail-closed review gates."""

    @staticmethod
    def _fingerprint(*parts: object) -> str:
        raw="|".join(str(x).strip() for x in parts)
        return "cand-"+sha256(raw.encode("utf-8")).hexdigest()[:16]

    def normalize(self, element, candidate: Mapping[str, object], *, accept_confidence=.80) -> NormalizedCandidate:
        if not 0 <= accept_confidence <= 1: raise ValueError("invalid confidence threshold")
        element_id=str(getattr(element,"element_id","")).strip()
        raw_sources=tuple(sorted({str(x).strip() for x in candidate.get("source_ids", getattr(element,"source_ids",())) if str(x).strip()}))
        raw_qty=candidate.get("quantity")
        qty=None
        if isinstance(raw_qty,(int,float)) and not isinstance(raw_qty,bool):
            qty=float(raw_qty)
        unit=str(candidate.get("unit") or "").strip()
        formula=str(candidate.get("formula") or "").strip()
        confidence=float(candidate.get("confidence",getattr(element,"confidence",0.0)))
        warnings=list(dict.fromkeys(str(x) for x in candidate.get("warnings",()) if str(x).strip()))
        if not element_id: warnings.append("عنصر مهندسی معتبر وجود ندارد")
        if qty is None: warnings.append("مقدار متره صریح وجود ندارد")
        elif not isfinite(qty) or qty < 0: warnings.append("مقدار متره نامعتبر است"); qty=None
        if not unit: warnings.append("واحد متره مشخص نیست")
        if not raw_sources: warnings.append("منبع نقشه برای ردیابی وجود ندارد")
        if confidence < accept_confidence: warnings.append("اعتماد کمتر از آستانه پذیرش است")
        if not element_id or qty is None or not unit or not raw_sources: status="rejected"
        elif confidence < accept_confidence: status="review"
        else: status="accepted"
        fp=self._fingerprint(element_id,qty,unit,formula,raw_sources,confidence,status)
        return NormalizedCandidate(element_id,qty,unit,formula,raw_sources,confidence,status,tuple(warnings),fp).validate()

    def coverage(self, source_ids: Sequence[str], elements: Sequence[object], quantities: Sequence[object]) -> tuple[TraceCoverage,...]:
        emap={}
        qmap={}
        for e in elements:
            for sid in getattr(e,"source_ids",()):
                sid=str(sid).strip()
                if sid: emap.setdefault(sid,[]).append(str(e.element_id))
        for q in quantities:
            for sid in getattr(q,"source_ids",()):
                sid=str(sid).strip()
                if sid: qmap.setdefault(sid,[]).append(str(getattr(q,"quantity_id",getattr(q,"fingerprint",""))))
        out=[]
        for sid in sorted({str(x).strip() for x in source_ids if str(x).strip()}):
            es=tuple(sorted(set(emap.get(sid,())))); qs=tuple(sorted(set(qmap.get(sid,()))))
            status="covered" if es and qs else "partial" if es or qs else "uncovered"
            if es and not qs: status="review"
            out.append(TraceCoverage(sid,es,qs,status,() if status=="covered" else ("منبع به مقدار پذیرفته‌شده متصل نیست",)).validate())
        return tuple(out)

    @staticmethod
    def unresolved(candidates: Sequence[NormalizedCandidate]) -> tuple[NormalizedCandidate,...]:
        return tuple(c for c in candidates if c.status != "accepted")

    @staticmethod
    def deterministic_order(candidates: Sequence[NormalizedCandidate]) -> tuple[NormalizedCandidate,...]:
        return tuple(sorted(candidates,key=lambda c:(c.element_id,c.fingerprint)))
