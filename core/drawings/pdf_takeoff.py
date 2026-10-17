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
        # This adapter is for *explicit* printed scales; discovering a scale
        # from surrounding text is a separate human-reviewed operation.
        if isinstance(scale, bool):
            raise ValueError("مقیاس نباید مقدار منطقی باشد")
        if isinstance(scale, (int, float)):
            factor = float(scale)
        else:
            match = re.fullmatch(r"\s*1\s*[:/]\s*(\d+(?:\.\d+)?)\s*", str(scale))
            if not match:
                raise ValueError("مقیاس باید صریح و یکتا به شکل 1:100 وارد شود")
            factor = float(match.group(1))
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("مقیاس باید مثبت و متناهی باشد")
        return factor

    @staticmethod
    def _measurement(value, name: str, *, allow_zero: bool = False) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{name}: مقدار عددی معتبر لازم است")
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{name}: مقدار عددی معتبر لازم است") from exc
        if not math.isfinite(result) or result < 0 or (result == 0 and not allow_zero):
            raise ValueError(f"{name}: مقدار باید مثبت و متناهی باشد")
        return result

    @staticmethod
    def _unit_divisor(unit: str) -> float:
        if unit not in {"m", "cm", "mm"}:
            raise ValueError("واحد نقشه باید صریحاً m، cm یا mm باشد")
        return {"m": 1.0, "cm": 100.0, "mm": 1000.0}[unit]

    def pixel_to_model(self,drawing_distance:float,scale:str|float,unit="m")->float:
        s = self.normalize_scale(scale)
        distance = self._measurement(drawing_distance, "فاصله نقشه")
        result = distance * s / self._unit_divisor(unit)
        return self._measurement(result, "فاصله واقعی")

    def measure_line(self,x1:float,y1:float,x2:float,y2:float,scale:str|float,unit="m")->Measurement:
        coords = [self._signed_coordinate(v) for v in (x1, y1, x2, y2)]
        return Measurement("length",self.pixel_to_model(math.hypot(coords[2]-coords[0],coords[3]-coords[1]),scale,unit),"m","pdf-scale",confidence=1.0)

    @staticmethod
    def _signed_coordinate(value) -> float:
        if isinstance(value, bool):
            raise ValueError("مختصات باید عددی باشند")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("مختصات باید متناهی باشند")
        return value

    def measure_area(self,drawing_area:float,scale:str|float,unit="m")->Measurement:
        s = self.normalize_scale(scale)
        area = self._measurement(drawing_area, "مساحت نقشه")
        result = area * s*s / self._unit_divisor(unit)**2
        return Measurement("area",self._measurement(result,"مساحت واقعی"),"m2","pdf-scale",confidence=1.0)

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
