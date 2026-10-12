"""P40 Drawing Intelligence 2.0: format/OCR evidence, scale and cross-sheet relationships."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
from .models import DrawingPrimitive
from .intelligence_v2 import DrawingIntelligenceV2

@dataclass(frozen=True)
class DrawingSource:
    path:str; format:str; page_count:int|None; confidence:float; evidence:tuple[str,...]
    def __post_init__(self):
        if self.format not in {"pdf","dwg","dxf","image","unknown"}: raise ValueError("unsupported format")
        if not 0<=self.confidence<=1: raise ValueError("invalid confidence")

@dataclass(frozen=True)
class OCRText:
    text:str; page:int|None; confidence:float
    def __post_init__(self):
        if not 0<=self.confidence<=1: raise ValueError("invalid confidence")

@dataclass(frozen=True)
class SheetRelation:
    left:str; right:str; relation:str; confidence:float
    def __post_init__(self):
        if not self.left or not self.right or self.left==self.right: raise ValueError("invalid sheet relation")
        if not 0<=self.confidence<=1: raise ValueError("invalid confidence")

_FORMATS={".pdf":"pdf",".dwg":"dwg",".dxf":"dxf",".png":"image",".jpg":"image",".jpeg":"image",".tif":"image",".tiff":"image"}

def inspect_source(path:str, *, page_count:int|None=None)->DrawingSource:
    ext=Path(path).suffix.casefold()
    fmt=_FORMATS.get(ext,"unknown")
    return DrawingSource(path,fmt,page_count,0.98 if fmt!="unknown" else 0.25,(f"extension={ext or 'none'}",))

def normalize_ocr(text:str, *, page:int|None=None, confidence:float=.75)->OCRText:
    cleaned=re.sub(r"[ \t]+"," ",str(text)).strip()
    return OCRText(cleaned,page,confidence)

def classify_sheets(primitives):
    return DrawingIntelligenceV2().detect_sheets(tuple(primitives))

def cross_sheet_relations(primitives, sheets):
    links=DrawingIntelligenceV2().link_semantics(tuple(primitives),tuple(sheets))
    return tuple(SheetRelation(link.key,link.sheet_ids[0], "shared-member-tag", link.confidence)
                 for link in links if link.sheet_ids)
