"""P141-P150 deterministic Drawing Intelligence generation 2."""
from __future__ import annotations
from dataclasses import dataclass
import re
from collections import defaultdict
from math import isfinite
_SCALE=re.compile(r"(?:1\s*[:/]\s*)(\d+(?:\.\d+)?)",re.I)
_SHEET=re.compile(r"\b([A-Z]{1,4})[-_ ]?(\d{1,4})\b")
_MEMBER=re.compile(r"^(?:B|BM|BEAM|C|COL|COLUMN|W|WALL|F|FTG|S|SLAB)[-_ ]?([A-Z0-9]+)$",re.I)
_TITLE_KEYS=("title","drawing title","project","پلان","مقطع","نما","عنوان")
@dataclass(frozen=True)
class SheetIdentity:
    sheet_id:str; page:int|None; title:str; confidence:float; evidence:tuple[str,...]
    def validate(self):
        if not self.sheet_id.strip() or not 0<=self.confidence<=1: raise ValueError("invalid sheet identity")
        return self
@dataclass(frozen=True)
class ScaleEvidence:
    denominator:float|None; confidence:float; source_id:str; reason:str
    def validate(self):
        if self.denominator is not None and (self.denominator<=0 or not isfinite(self.denominator)): raise ValueError("invalid scale")
        if not 0<=self.confidence<=1: raise ValueError("invalid confidence")
        return self
@dataclass(frozen=True)
class SemanticLink:
    key:str; source_ids:tuple[str,...]; sheet_ids:tuple[str,...]; confidence:float; evidence:tuple[str,...]
    def validate(self):
        if not self.key.strip() or not self.source_ids: raise ValueError("invalid semantic link")
        return self
@dataclass(frozen=True)
class RecognitionDecision:
    source_id:str; action:str; confidence:float; reasons:tuple[str,...]
    def validate(self):
        if self.action not in {"accept","review","reject"} or not 0<=self.confidence<=1: raise ValueError("invalid recognition decision")
        return self
class DrawingIntelligenceV2:
    def detect_sheets(self,primitives):
        groups=defaultdict(list)
        for p in primitives: groups[_page(p)].append(p)
        if not groups: groups[None]=[]
        out=[]
        for page,items in groups.items():
            candidates=[(p,_SHEET.search(p.text.strip()).group(0)) for p in items if p.normalized_kind()=="text" and _SHEET.search(p.text.strip())]
            if candidates:
                p,sid=candidates[0]
                title=next((x.text.strip() for x in items if any(k in x.text.casefold() for k in _TITLE_KEYS)),p.text.strip())
                out.append(SheetIdentity(sid.upper(),page,title,.90,(f"text={sid}",)).validate())
            else: out.append(SheetIdentity(f"PAGE-{page or 1}",page,"",.55,("page fallback",)).validate())
        return tuple(out)
    def infer_scale(self,primitives,metadata=None):
        ev=[]
        if metadata:
            try:
                if metadata.get("scale_denominator") is not None: ev.append(ScaleEvidence(float(metadata["scale_denominator"]),.98,"metadata","explicit metadata"))
            except (TypeError,ValueError): pass
        for p in primitives:
            if p.normalized_kind()=="text":
                m=_SCALE.search(p.text)
                if m: ev.append(ScaleEvidence(float(m.group(1)),.94,p.source_id,"scale notation"))
        return max(ev,key=lambda x:x.confidence).validate() if ev else ScaleEvidence(None,0.0,"","scale not found").validate()
    def recognize(self,primitives):
        out=[]
        for p in primitives:
            if not p.source_id: out.append(RecognitionDecision("", "reject",0.0,("missing source identity",))); continue
            c=0.0; r=[]
            if p.layer.strip(): c=max(c,.55); r.append("layer evidence")
            if p.text.strip(): c=max(c,.70); r.append("text evidence")
            if p.text.strip() and _MEMBER.match(p.text.strip()): c=max(c,.90); r.append("member tag")
            if p.normalized_kind() in {"line","polyline","circle","rectangle"}: c=max(c,.60); r.append("geometry evidence")
            elif p.normalized_kind(): c=max(c,.50); r.append("unclassified geometry; review required")
            a="accept" if c>=.85 else "review" if c>=.50 else "reject"
            out.append(RecognitionDecision(p.source_id,a,c,tuple(r)).validate())
        return tuple(out)
    def link_semantics(self,primitives,sheets=None):
        buckets=defaultdict(list); sheet_by_page={s.page:s.sheet_id for s in (sheets or ())}
        for p in primitives:
            m=_MEMBER.match(p.text.strip()) if p.text.strip() else None
            if m: buckets[m.group(1).upper()].append(p)
        out=[]
        for key,items in sorted(buckets.items()):
            ids=tuple(dict.fromkeys(p.source_id for p in items if p.source_id))
            pages=tuple(dict.fromkeys(sheet_by_page.get(_page(p)) for p in items if sheet_by_page.get(_page(p))))
            out.append(SemanticLink(key,ids,pages,.92,("normalized member tag",)).validate())
        return tuple(out)
    def suppress_duplicates(self,primitives):
        seen=set(); out=[]
        for p in primitives:
            key=(p.normalized_kind(),round(p.x,6),round(p.y,6),round(p.x2,6),round(p.y2,6),round(p.width,6),round(p.height,6),p.text.strip().casefold(),p.layer.strip().casefold())
            if key not in seen: seen.add(key); out.append(p)
        return tuple(out)
def _page(p):
    try: return int(p.properties.get("page")) if p.properties.get("page") is not None else None
    except (TypeError,ValueError): return None
