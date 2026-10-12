"""Human-in-the-loop drawing takeoff review and recognition utilities."""
from __future__ import annotations
from dataclasses import dataclass
import re
from .models import DrawingPrimitive, EngineeringElement

@dataclass(frozen=True)
class ReviewItem:
    source_id: str
    kind: str
    reason: str
    confidence: float
    page: int|None=None

_DIMENSION_PATTERNS=(
    re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:mm|cm|m)\b",re.I),
    re.compile(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*[×x]\s*(\d+(?:[.,]\d+)?)",re.I),
)
_GRID=re.compile(r"^(?:[A-Z]{1,3}|\d{1,3})$")
_LEVEL=re.compile(r"(?:LEVEL|L|تراز|طبقه)\s*[-+]?\s*(\d+(?:[.,]\d+)?)",re.I)

def _page(p):
    value=p.properties.get("page")
    try:return int(value) if value is not None else None
    except (TypeError,ValueError):return None

def recognize_text(primitives):
    rows=[]
    for p in primitives:
        if p.normalized_kind()!="text" or not p.text.strip(): continue
        t=p.text.strip()
        page=_page(p)
        for rx in _DIMENSION_PATTERNS:
            if rx.search(t):
                rows.append(ReviewItem(p.source_id,"dimension","dimension text detected",0.92,page)); break
        if _LEVEL.search(t):
            rows.append(ReviewItem(p.source_id,"level","level text detected",0.90,page))
        elif _GRID.fullmatch(t):
            rows.append(ReviewItem(p.source_id,"grid","possible grid label; requires review",0.65,page))
    return tuple(rows)

def review_queue(primitives, elements):
    known={s for e in elements for s in e.source_ids}
    rows=list(recognize_text(primitives))
    for p in primitives:
        if p.source_id not in known and p.normalized_kind() in {"line","polyline","rectangle","circle"}:
            rows.append(ReviewItem(p.source_id,"unclassified_geometry",
                "graphical geometry requires human classification",0.35,_page(p)))
    return tuple(rows)

@dataclass
class DrawingTakeoffSelection:
    """Explicit selection model used by a future viewer and safe for automation."""
    selected_source_ids:set[str]
    def __init__(self, selected_source_ids=()):
        self.selected_source_ids=set(selected_source_ids)
    def select(self, source_id): self.selected_source_ids.add(str(source_id))
    def deselect(self, source_id): self.selected_source_ids.discard(str(source_id))
    def clear(self): self.selected_source_ids.clear()
    def apply(self, primitives):
        ids=self.selected_source_ids
        return tuple(p for p in primitives if p.source_id in ids)

def build_review(primitives, elements):
    return review_queue(primitives,elements)
