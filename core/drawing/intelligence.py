"""Rule-based drawing-to-engineering classification.

This is intentionally deterministic and auditable. It does not perform structural
analysis/design and never invents dimensions that are absent from the drawing.
"""
from __future__ import annotations
import re
from .models import DrawingPrimitive, EngineeringElement

_LAYER_RULES = (
    (re.compile(r"(^|[-_ ])(beam|girder|tiebeam|تیر)([-_ ]|$)", re.I), "concrete", "beam"),
    (re.compile(r"(^|[-_ ])(column|col|ستون)([-_ ]|$)", re.I), "concrete", "column"),
    (re.compile(r"(^|[-_ ])(slab|deck|دال)([-_ ]|$)", re.I), "concrete", "slab"),
    (re.compile(r"(^|[-_ ])(wall|shearwall|دیوار)([-_ ]|$)", re.I), "concrete", "wall"),
    (re.compile(r"(^|[-_ ])(footing|foundation|پی|فونداسیون)([-_ ]|$)", re.I), "foundations", "isolated"),
    (re.compile(r"(^|[-_ ])(steel|stl|فولاد)([-_ ]|$)", re.I), "steel", "member"),
)

_TEXT_RULES = (
    (re.compile(r"\b(?:B|BM|BEAM|GIRDER)[-_ ]?\d+\b", re.I), "concrete", "beam"),
    (re.compile(r"\b(?:C|COL|COLUMN)[-_ ]?\d+\b", re.I), "concrete", "column"),
    (re.compile(r"\b(?:W|WALL)[-_ ]?\d+\b", re.I), "concrete", "wall"),
    (re.compile(r"\b(?:F|FTG|FOOTING)[-_ ]?\d+\b", re.I), "foundations", "isolated"),
    (re.compile(r"(?:تیر|ستون|دال|دیوار|فونداسیون|پی)\s*[-_]?\s*\d+", re.I), "concrete", "member"),
)

def _bbox(p: DrawingPrimitive) -> dict[str, float]:
    if p.normalized_kind() in {"line", "polyline"}:
        length=((p.x2-p.x)**2+(p.y2-p.y)**2)**0.5
        return {"x":p.x,"y":p.y,"length":length}
    return {"x":p.x,"y":p.y,"width":abs(p.width),"height":abs(p.height)}

def _match(p: DrawingPrimitive):
    layer=p.layer.strip()
    for rx,domain,kind in _LAYER_RULES:
        if layer and rx.search(layer): return domain,kind,("layer",layer),0.95
    text=p.text.strip()
    for rx,domain,kind in _TEXT_RULES:
        if text and rx.search(text): return domain,kind,("text",text),0.90
    return None

def classify_primitives(primitives) -> tuple[EngineeringElement, ...]:
    result=[]
    for index,p in enumerate(primitives,1):
        if not isinstance(p,DrawingPrimitive): raise TypeError("primitives must contain DrawingPrimitive")
        matched=_match(p)
        if matched is None: continue
        domain,kind,evidence,confidence=matched
        result.append(EngineeringElement(
            element_id=p.source_id or f"DRAW-{index:04d}",
            domain=domain,kind=kind,source_ids=(p.source_id,) if p.source_id else (),
            geometry=_bbox(p),confidence=confidence,evidence=(f"{evidence[0]}={evidence[1]}",),
            properties=dict(p.properties),
        ).validate())
    return tuple(result)

class DrawingIntelligence:
    """Facade for normalized drawing classification and traceability."""

    def classify(self, primitives) -> tuple[EngineeringElement, ...]:
        return classify_primitives(primitives)

    def summary(self, primitives) -> dict[str, int]:
        elements=self.classify(primitives)
        result={}
        for e in elements: result[e.kind]=result.get(e.kind,0)+1
        return dict(sorted(result.items()))
