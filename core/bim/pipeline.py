"""Operational BIM -> quantity -> BOQ pipeline with fail-closed geometry."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from .ifc import DeepIFCAdapter
from .takeoff import quantities
from core.takeoff.drawing_pipeline import DrawingTakeoffPipeline

@dataclass(frozen=True)
class BIMPipelineResult:
    elements: tuple
    quantities: tuple
    boq: tuple[dict,...]
    warnings: tuple[str,...]

class BIMTakeoffPipeline:
    def __init__(self, adapter=None, price_resolver:Callable[[str],float|None]|None=None):
        self.adapter=adapter or DeepIFCAdapter()
        self.boq_engine=DrawingTakeoffPipeline(price_resolver=price_resolver)
    def process(self,path):
        elements=self.adapter.read(path)
        qs=quantities(elements)
        rows=[{"source":q.source_id,"description":q.description,"quantity":q.quantity,
               "unit":q.unit,"price_code":q.item_code} for q in qs]
        boq=tuple(self.boq_engine.to_boq(self.boq_engine.normalize(rows)))
        unresolved=tuple(f"IFC element has no explicit quantity geometry: {e.global_id}" for e in elements if not e.has_explicit_quantity_geometry)
        return BIMPipelineResult(tuple(elements),tuple(qs),boq,unresolved)
