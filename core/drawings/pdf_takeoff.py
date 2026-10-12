"""Offline PDF plan takeoff primitives: pages, scale, dimensions and measurements."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from core.drawings.graphical_takeoff import ScaleCalibration, Point, MeasurementStore, subtract_areas
import re, math

@dataclass(frozen=True)
class PDFPageInfo:
    page:int; width:float|None; height:float|None; text:str

@dataclass(frozen=True)
class Measurement:
    kind:str; value:float; unit:str; source:str; page:int|None=None; label:str=""; confidence:float=1.0

_DIM_RE=re.compile(r"(?P<label>[A-Za-zآ-ی0-9_\- ]{0,40})?\s*(?P<value>\d+(?:[\.,]\d+)?)\s*(?P<unit>mm|cm|m|متر|سانت|میلی?متر)",re.I)

class PDFTakeoffAdapter:
    def inspect(self,path:str|Path)->list[PDFPageInfo]:
        p=Path(path)
        if not p.exists():raise FileNotFoundError(p)
        try:from pypdf import PdfReader
        except ImportError as exc:raise RuntimeError("pypdf is required") from exc
        reader=PdfReader(str(p)); out=[]
        for i,page in enumerate(reader.pages,1):
            box=page.mediabox; out.append(PDFPageInfo(i,float(box.width),float(box.height),page.extract_text() or ""))
        return out

    @staticmethod
    def normalize_scale(scale:str|float)->float:
        if isinstance(scale,(int,float)): return float(scale)
        m=re.search(r"1\s*[:/]\s*(\d+(?:\.\d+)?)",str(scale))
        if not m: raise ValueError("Scale must look like 1:100")
        return float(m.group(1))

    def pixel_to_model(self,drawing_distance:float,scale:str|float,unit="m")->float:
        s=self.normalize_scale(scale); value=float(drawing_distance)*s
        if unit=="mm": return value/1000
        if unit=="cm": return value/100
        return value

    def measure_line(self,x1:float,y1:float,x2:float,y2:float,scale:str|float,unit="m")->Measurement:
        return Measurement("length",self.pixel_to_model(math.hypot(x2-x1,y2-y1),scale,unit),"m","pdf-scale",confidence=1.0)

    def measure_area(self,drawing_area:float,scale:str|float,unit="m")->Measurement:
        s=self.normalize_scale(scale); value=float(drawing_area)*s*s
        if unit=="mm": value/=1_000_000
        elif unit=="cm": value/=10_000
        return Measurement("area",value,"m2","pdf-scale",confidence=1.0)

    def calibrate(self, scale, drawing_unit="cm", model_unit="m"):
        return ScaleCalibration.parse(scale, drawing_unit, model_unit)

    def graphical_line(self, points, scale, page=None, label="", layer=None):
        store=MeasurementStore(); cal=self.calibrate(scale)
        return store.add_length([Point(float(x),float(y)) for x,y in points], cal,
                                page=page, label=label, layer=layer, source="pdf-graphical")

    def graphical_area(self, points, scale, holes=(), page=None, label="", layer=None):
        store=MeasurementStore(); cal=self.calibrate(scale)
        return store.add_area([Point(float(x),float(y)) for x,y in points], cal, holes=holes,
                              page=page, label=label, layer=layer, source="pdf-graphical")

    def net_area(self, gross, holes):
        return subtract_areas(gross, holes)

    def measurements(self,pages:Iterable[PDFPageInfo])->list[Measurement]:
        out=[]
        for page in pages:
            for m in _DIM_RE.finditer(page.text):
                value=float(m.group("value").replace(",",".")); u=m.group("unit").lower()
                if u in ("mm","میلیمتر"):value/=1000
                elif u in ("cm","سانت"):value/=100
                out.append(Measurement("dimension",value,"m","pdf-text",page.page,(m.group("label") or "").strip(),0.45))
        return out

    def text_takeoff_candidates(self,pages:Iterable[PDFPageInfo])->list[dict]:
        return [{
            "source": f"pdf:p{m.page}",
            "description": m.label or "dimension",
            "quantity": m.value,
            "unit": m.unit,
            "confidence": m.confidence,
            "page": m.page,
            "sheet": f"p{m.page}",
            "needs_confirmation": True,
        } for m in self.measurements(pages)]
