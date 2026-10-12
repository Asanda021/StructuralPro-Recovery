"""P151-P160 production drawing workflow and advanced deterministic recognition."""
from __future__ import annotations
from dataclasses import dataclass
import re
from collections import defaultdict
from math import isfinite
from typing import Iterable
from .models import DrawingPrimitive, EngineeringElement

_DIM = re.compile(r"(?<![A-Za-z0-9])(?:DIM|D|DIMENSION)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:mm|cm|m)?\b", re.I)
_AXIS = re.compile(r"^(?:AXIS|GRID|محور)\s*[-_ ]?([A-Z0-9]+)$", re.I)
_ROOM = re.compile(r"^(?:ROOM|ZONE|فضا|اتاق)\s*[-_ ]?([A-Z0-9آ-ی]+)$", re.I)

@dataclass(frozen=True)
class DimensionEvidence:
    value: float
    source_id: str
    unit: str
    confidence: float
    evidence: tuple[str, ...] = ()
    def validate(self):
        if not isfinite(self.value) or self.value <= 0: raise ValueError("dimension must be positive and finite")
        if not self.source_id.strip() or self.unit not in {"mm","cm","m","unknown"}: raise ValueError("invalid dimension evidence")
        if not 0 <= self.confidence <= 1: raise ValueError("confidence must be between 0 and 1")
        return self

@dataclass(frozen=True)
class AxisGrid:
    key: str; source_ids: tuple[str,...]; sheet_ids: tuple[str,...]; confidence: float
    def validate(self):
        if not self.key.strip() or not self.source_ids: raise ValueError("axis/grid identity is required")
        if not 0 <= self.confidence <= 1: raise ValueError("confidence must be between 0 and 1")
        return self

@dataclass(frozen=True)
class ZoneIdentity:
    key: str; source_ids: tuple[str,...]; sheet_ids: tuple[str,...]; confidence: float
    def validate(self):
        if not self.key.strip() or not self.source_ids: raise ValueError("zone identity is required")
        if not 0 <= self.confidence <= 1: raise ValueError("confidence must be between 0 and 1")
        return self

@dataclass(frozen=True)
class Correction:
    source_id: str; field: str; old_value: str; new_value: str; actor: str = "human"

class DrawingProductionWorkflow:
    """Fail-closed production layer on top of DrawingIntelligenceV2."""
    def extract_dimensions(self, primitives: Iterable[DrawingPrimitive]):
        out=[]
        for p in primitives:
            if p.normalized_kind()!="text" or not p.source_id: continue
            text=p.text.strip(); match=_DIM.search(text)
            if not match: continue
            value=float(match.group(1)); low=text.casefold(); unit="unknown"
            if "mm" in low: unit="mm"
            elif "cm" in low: unit="cm"
            elif re.search(r"\bm\b",low): unit="m"
            out.append(DimensionEvidence(value,p.source_id,unit,.95,("explicit dimension text",)).validate())
        return tuple(out)

    def infer_axes(self, primitives, sheets=()):
        by_key=defaultdict(list); sheet_by_page={s.page:s.sheet_id for s in sheets}
        for p in primitives:
            if p.source_id and p.text.strip():
                m=_AXIS.match(p.text.strip())
                if m: by_key[m.group(1).upper()].append(p)
        out=[]
        for key,items in sorted(by_key.items()):
            ids=tuple(dict.fromkeys(p.source_id for p in items))
            sids=tuple(dict.fromkeys(sheet_by_page.get(_page(p)) for p in items if sheet_by_page.get(_page(p))))
            out.append(AxisGrid(key,ids,sids,.93).validate())
        return tuple(out)

    def infer_zones(self, primitives, sheets=()):
        by_key=defaultdict(list); sheet_by_page={s.page:s.sheet_id for s in sheets}
        for p in primitives:
            if p.source_id and p.text.strip():
                m=_ROOM.match(p.text.strip())
                if m: by_key[m.group(1).upper()].append(p)
        out=[]
        for key,items in sorted(by_key.items()):
            ids=tuple(dict.fromkeys(p.source_id for p in items))
            sids=tuple(dict.fromkeys(sheet_by_page.get(_page(p)) for p in items if sheet_by_page.get(_page(p))))
            out.append(ZoneIdentity(key,ids,sids,.90).validate())
        return tuple(out)

    def recognize_elements(self, primitives):
        out=[]; seen=set()
        for p in primitives:
            if not p.source_id or p.source_id in seen: continue
            seen.add(p.source_id); text=p.text.strip(); kind=p.normalized_kind()
            member=re.match(r"^(?:B|BM|BEAM|C|COL|COLUMN|W|WALL|F|FTG|S|SLAB)[-_ ]?([A-Z0-9]+)$",text,re.I)
            if member:
                domain="structural"; ekind="member"; confidence=.94; evidence=("explicit member tag",)
            elif kind in {"line","polyline","rectangle","circle"} and p.layer.strip():
                domain="drawing"; ekind=kind; confidence=.72; evidence=("geometry + layer evidence",)
            else: continue
            geometry={"x":float(p.x),"y":float(p.y),"x2":float(p.x2),"y2":float(p.y2)}
            out.append(EngineeringElement(f"DRAW-{p.source_id}",domain,ekind,(p.source_id,),geometry,confidence,evidence,{"member_key":member.group(1).upper() if member else ""}).validate())
        return tuple(out)

    def reconcile_sources(self, elements):
        index=defaultdict(list)
        for e in elements:
            for sid in e.source_ids: index[sid].append(e.element_id)
        return {sid:tuple(sorted(ids)) for sid,ids in sorted(index.items())}

    def apply_correction(self, correction, allowed_fields=frozenset({"label","zone","axis"})):
        if not correction.source_id.strip() or correction.field not in allowed_fields: raise ValueError("unsupported human correction")
        if not correction.new_value.strip(): raise ValueError("correction value is required")
        return correction

def _page(p):
    try: return int(p.properties.get("page")) if p.properties.get("page") is not None else None
    except (TypeError,ValueError): return None
