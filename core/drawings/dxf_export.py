"""DXF/DWG interchange helpers with explicit unit/layer provenance."""
from __future__ import annotations
from pathlib import Path
from typing import Iterable
from core.drawings.dwg_takeoff import DWGDocument

class DXFTakeoffExporter:
    def export_summary(self,doc:DWGDocument,path:str|Path)->Path:
        p=Path(path)
        rows=["StructuralPro CAD Takeoff Summary","Layer,Entity,Handle,Metric"]
        for e in doc.entities:
            metric=e.data.get("length",e.data.get("area",1))
            rows.append(f'"{e.layer}","{e.entity_type}","{e.handle or ""}",{metric}')
        p.write_text("\n".join(rows),encoding="utf-8")
        return p
