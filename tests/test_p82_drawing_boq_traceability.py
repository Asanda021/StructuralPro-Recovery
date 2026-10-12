import pytest
from core.drawing.adapters import AdapterResult, DrawingAdapterRegistry, DrawingSource
from core.drawing.models import DrawingPrimitive
from core.drawing.pipeline import DrawingIntelligencePipeline

class FakeTraceAdapter:
    extensions = (".p82",)
    def read(self, path):
        return AdapterResult(DrawingSource(path, "p82", {}), (
            DrawingPrimitive("line", x=0, y=0, x2=6000, y2=0, layer="BEAM", source_id="p82:beam:1"),
        ))

def test_p82_traceability_is_complete_from_drawing_to_boq(tmp_path):
    path=tmp_path/"plan.p82"; path.write_text("placeholder", encoding="utf-8")
    result=DrawingIntelligencePipeline(adapters=DrawingAdapterRegistry(adapters=(FakeTraceAdapter(),))).process(str(path), unit="mm")
    graph=result.trace_graph
    assert graph.validate()["valid"]
    stages={node.stage for node in graph.nodes.values()}
    assert {"drawing","model","takeoff","boq"} <= stages
    boq=next(n for n in graph.nodes.values() if n.stage=="boq")
    lineage=graph.lineage(boq.node_id)
    lineage_stages=[graph.nodes[n].stage for n in lineage]
    assert lineage_stages == ["drawing","model","takeoff"]
    assert result.audit_trail.events() == []

def test_p82_unscaled_drawing_has_no_measurement_lineage(tmp_path):
    path=tmp_path/"plan.p82"; path.write_text("placeholder", encoding="utf-8")
    result=DrawingIntelligencePipeline(adapters=DrawingAdapterRegistry(adapters=(FakeTraceAdapter(),))).process(str(path))
    assert result.trace_graph.validate()["valid"]
    assert {node.stage for node in result.trace_graph.nodes.values()} == {"drawing"}
    assert result.boq == ()
