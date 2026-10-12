"""Offline graphical PDF measurement adapter.
Uses PyMuPDF when installed; measurement itself is deterministic and can also run
against externally supplied page geometry without a rendering dependency.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import math

@dataclass(frozen=True)
class PageGeometry:
    page:int
    width_pt:float
    height_pt:float

@dataclass(frozen=True)
class GraphicMeasurement:
    page:int
    kind:str
    quantity:float
    unit:str
    confidence:float
    points:tuple[tuple[float,float],...]=()

class GraphicalPDFTakeoff:
    def inspect_geometry(self,path:str|Path)->list[PageGeometry]:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required for graphical PDF inspection") from exc
        doc=fitz.open(str(path))
        return [PageGeometry(i+1,float(p.rect.width),float(p.rect.height)) for i,p in enumerate(doc)]

    @staticmethod
    def line(page,x1,y1,x2,y2,scale,unit="m"):
        s=float(scale); px=math.hypot(x2-x1,y2-y1); q=px*s
        if unit=="mm": q/=1000
        elif unit=="cm": q/=100
        return GraphicMeasurement(page,"length",q,"m",1.0,((x1,y1),(x2,y2)))

    @staticmethod
    def polygon(page,points,scale,unit="m2"):
        pts=list(points); area=abs(sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))/2)
        q=area*float(scale)**2
        if unit=="mm2": q/=1_000_000
        elif unit=="cm2": q/=10_000
        return GraphicMeasurement(page,"area",round(q,10),"m2",1.0,tuple(pts))
