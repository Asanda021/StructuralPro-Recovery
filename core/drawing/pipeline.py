"""Operational source-to-BOQ drawing pipeline with measurement and lineage integrity."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from core.audit.traceability import AuditTrail, TraceNode, TraceGraph, stable_id
from core.standards import StandardsEngine, default_iran_registry
from core.takeoff.drawing_pipeline import DrawingTakeoffPipeline
from .adapters import AdapterResult, DrawingAdapterRegistry
from .intelligence import DrawingIntelligence
from .takeoff import drawing_takeoff
from .measurement_pipeline import DrawingMeasurementGate

@dataclass(frozen=True)
class DrawingPipelineResult:
    source: Any
    adapter_warnings: tuple[str, ...]
    measurement_warnings: tuple[str, ...]
    scale: Any
    primitives: tuple
    elements: tuple
    quantity_candidates: tuple[dict, ...]
    standards: dict[str, tuple[dict, ...]]
    boq: tuple[dict, ...]
    trace_graph: TraceGraph
    audit_trail: AuditTrail

class DrawingIntelligencePipeline:
    """Run drawing source -> measured elements -> takeoff -> BOQ with immutable lineage."""
    def __init__(self, adapters=None, standards_engine=None, price_resolver: Callable[[str], float | None] | None = None):
        self.adapters = adapters or DrawingAdapterRegistry()
        self.standards = standards_engine or StandardsEngine(default_iran_registry())
        self.takeoff_pipeline = DrawingTakeoffPipeline(price_resolver=price_resolver)
        self.intelligence = DrawingIntelligence()
        self.measurement_gate = DrawingMeasurementGate(self.adapters)

    @staticmethod
    def _standard_domain(domain: str) -> str:
        return "foundations" if domain == "foundations" else domain

    @staticmethod
    def _source_for(element) -> str:
        return element.source_ids[0] if element.source_ids else element.element_id

    def _build_trace(self, adapted, elements, candidates, boq_rows):
        graph = TraceGraph()
        trail = AuditTrail()
        source_nodes = {}
        for primitive in adapted.primitives:
            source = primitive.source_id.strip() or f"{adapted.source.path}:{primitive.kind}"
            node_id = stable_id("drawing", str(adapted.source.path), source)
            source_nodes[source] = node_id
            graph.add_node(TraceNode(node_id=node_id, stage="drawing", source=str(adapted.source.path), external_id=source))
        element_nodes = {}
        for element in elements:
            node_id = stable_id("model", str(adapted.source.path), element.element_id)
            element_nodes[element.element_id] = node_id
            graph.add_node(TraceNode(
                node_id=node_id, stage="model", source=str(adapted.source.path),
                external_id=element.element_id, discipline=element.domain,
            ))
            for source in element.source_ids:
                parent = source_nodes.get(source)
                if parent:
                    graph.link(parent, node_id)
        takeoff_nodes = {}
        takeoff_by_source = {}
        for candidate in candidates:
            element_id = candidate["element_id"]
            node_id = stable_id("takeoff", str(adapted.source.path), element_id)
            takeoff_nodes[element_id] = node_id
            takeoff_by_source[self._source_for(next(e for e in elements if e.element_id == element_id))] = node_id
            graph.add_node(TraceNode(
                node_id=node_id, stage="takeoff", source=str(adapted.source.path),
                external_id=element_id, discipline=candidate["domain"],
                quantity=candidate["quantity"], unit=candidate["unit"],
            ))
            parent = element_nodes.get(element_id)
            if parent:
                graph.link(parent, node_id)
        for row in boq_rows:
            source = str(row["source"])
            element_id = source
            node_id = stable_id("boq", str(adapted.source.path), source)
            graph.add_node(TraceNode(
                node_id=node_id, stage="boq", source=str(adapted.source.path),
                external_id=source, quantity=row["quantity"], unit=row["unit"],
                item_code=str(row.get("price_code") or ""),
            ))
            parent = takeoff_nodes.get(element_id) or takeoff_by_source.get(source)
            if parent:
                graph.link(parent, node_id)
        return graph, trail

    def process(self, path: str, *, unit=None, scale_denominator=None) -> DrawingPipelineResult:
        adapted: AdapterResult = self.adapters.read(path)
        scale, elements, measurement_warnings = self.measurement_gate.apply(
            adapted, unit=unit, scale_denominator=scale_denominator
        )
        candidates = drawing_takeoff(elements) if scale is not None else ()
        standard_map: dict[str, tuple[dict, ...]] = {}
        for element in elements:
            try:
                decisions = self.standards.resolve(domain=self._standard_domain(element.domain))
            except (LookupError, ValueError):
                decisions = ()
            standard_map[element.element_id] = tuple({
                "rule_code": d.rule_code, "source_code": d.source_code,
                "source_title": d.source_title, "edition": d.edition,
                "clause": d.clause, "topic": d.topic, "requirement": d.requirement,
            } for d in decisions)
        rows = []
        for candidate in candidates:
            if candidate["quantity"] is None:
                continue
            rows.append({
                "source": self._source_for(next(e for e in elements if e.element_id == candidate["element_id"])),
                "description": f"{candidate['domain']}:{candidate['kind']}",
                "quantity": candidate["quantity"], "unit": candidate["unit"],
            })
        boq_rows = self.takeoff_pipeline.to_boq(self.takeoff_pipeline.normalize(rows))
        trace_graph, audit_trail = self._build_trace(adapted, elements, candidates, boq_rows)
        return DrawingPipelineResult(
            source=adapted.source, adapter_warnings=adapted.warnings,
            measurement_warnings=tuple(measurement_warnings), scale=scale,
            primitives=adapted.primitives, elements=elements,
            quantity_candidates=candidates, standards=standard_map,
            boq=tuple(boq_rows), trace_graph=trace_graph, audit_trail=audit_trail,
        )
