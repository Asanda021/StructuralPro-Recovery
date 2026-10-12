"""Phase 18 PDF takeoff workbench.

A deterministic orchestration layer over the existing PDF measurement engine.
It covers sheet management, scale, length/area/volume/count, markup, crop/cutout,
measurement history and undo/redo without guessing engineering quantities.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from copy import deepcopy
from typing import Any

@dataclass(frozen=True)
class Sheet:
    id: str
    page: int
    title: str = ""

@dataclass(frozen=True)
class Markup:
    id: str
    kind: str
    page: int
    data: dict[str, Any]

class PDFTakeoffWorkbench:
    def __init__(self):
        self.sheets: list[Sheet] = []
        self.measurements: list[dict[str, Any]] = []
        self.markups: list[Markup] = []
        self.crops: list[dict[str, Any]] = []
        self.cutouts: list[dict[str, Any]] = []
        self.scale: float | None = None
        self.scale_source: str | None = None
        self._undo: list[dict[str, Any]] = []
        self._redo: list[dict[str, Any]] = []

    def _snapshot(self):
        return {"sheets":deepcopy(self.sheets),"measurements":deepcopy(self.measurements),
                "markups":deepcopy(self.markups),"crops":deepcopy(self.crops),
                "cutouts":deepcopy(self.cutouts),"scale":self.scale,"scale_source":self.scale_source}

    def _record(self):
        self._undo.append(self._snapshot()); self._redo.clear()

    def set_scale(self, units_per_page_unit: float, source: str):
        if units_per_page_unit <= 0 or not source.strip(): raise ValueError("valid scale and source required")
        self._record(); self.scale=float(units_per_page_unit); self.scale_source=source.strip(); return self.scale

    def add_sheet(self, page: int, title: str = "", sheet_id: str | None = None):
        if page < 1: raise ValueError("page must be >= 1")
        if any(x.page == page for x in self.sheets): raise ValueError("page already exists")
        self._record(); s=Sheet(sheet_id or f"S{len(self.sheets)+1}",page,title); self.sheets.append(s); return s

    def add_measurement(self, kind: str, value: float, unit: str, page: int, *, label="", source="manual"):
        if kind not in {"length","area","volume","count"}: raise ValueError("unsupported measurement kind")
        if value < 0 or page < 1: raise ValueError("invalid measurement")
        self._record(); m={"id":f"M{len(self.measurements)+1}","kind":kind,"value":float(value),
                            "unit":unit,"page":int(page),"label":label,"source":source}
        self.measurements.append(m); return deepcopy(m)

    def add_markup(self, kind: str, page: int, data: dict[str,Any], markup_id: str | None=None):
        if page < 1 or not kind.strip(): raise ValueError("invalid markup")
        self._record(); m=Markup(markup_id or f"MK{len(self.markups)+1}",kind,page,deepcopy(data)); self.markups.append(m); return m

    def add_crop(self, page:int, bounds:tuple[float,float,float,float]):
        if len(bounds)!=4 or bounds[2]<=bounds[0] or bounds[3]<=bounds[1]: raise ValueError("invalid crop")
        self._record(); x={"page":page,"bounds":tuple(float(v) for v in bounds)}; self.crops.append(x); return x

    def add_cutout(self, page:int, polygon:list[tuple[float,float]]):
        if len(polygon)<3: raise ValueError("cutout requires polygon")
        self._record(); x={"page":page,"polygon":[(float(a),float(b)) for a,b in polygon]}; self.cutouts.append(x); return x

    def remove_measurement(self, measurement_id:str):
        self._record(); old=len(self.measurements); self.measurements=[x for x in self.measurements if x["id"]!=measurement_id]
        if len(self.measurements)==old: self._undo.pop(); return False
        return True

    def undo(self):
        if not self._undo: return False
        current=self._snapshot(); previous=self._undo.pop(); self._redo.append(current); self.__dict__.update(deepcopy(previous)); return True

    def redo(self):
        if not self._redo: return False
        current=self._snapshot(); nxt=self._redo.pop(); self._undo.append(current); self.__dict__.update(deepcopy(nxt)); return True

    def history(self): return {"undo_available":len(self._undo),"redo_available":len(self._redo),
                               "measurements":len(self.measurements),"markups":len(self.markups)}

    def export(self):
        return {"scale":{"value":self.scale,"source":self.scale_source},
                "sheets":[asdict(x) for x in self.sheets],"measurements":deepcopy(self.measurements),
                "markups":[asdict(x) for x in self.markups],"crops":deepcopy(self.crops),"cutouts":deepcopy(self.cutouts)}
