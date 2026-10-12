"""Immutable project-wide lineage and audit trail.

The audit layer connects Drawing -> Model -> Takeoff -> BOQ -> Estimate ->
Revision without assuming a particular construction discipline.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Iterable, Mapping, Any
from datetime import datetime, timezone
import hashlib, json, math

STAGES = ("drawing", "model", "takeoff", "boq", "estimate", "revision")

def stable_id(stage: str, source: str, external_id: str = "") -> str:
    raw = "|".join((stage.strip().lower(), source.strip(), external_id.strip()))
    if not raw.strip("|"):
        raise ValueError("stage/source/external_id cannot all be empty")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

@dataclass(frozen=True)
class TraceNode:
    node_id: str
    stage: str
    discipline: str = ""
    source: str = ""
    external_id: str = ""
    revision: str = ""
    quantity: float | None = None
    unit: str = ""
    item_code: str = ""

    def validate(self) -> "TraceNode":
        stage = self.stage.strip().lower()
        if stage not in STAGES:
            raise ValueError(f"unsupported trace stage: {self.stage}")
        quantity = None if self.quantity is None else float(self.quantity)
        if quantity is not None and (not math.isfinite(quantity) or quantity < 0):
            raise ValueError("quantity must be finite and non-negative")
        node_id = self.node_id.strip() or stable_id(stage, self.source, self.external_id)
        if not node_id:
            raise ValueError("node_id is required")
        return TraceNode(node_id=node_id, stage=stage, discipline=self.discipline.strip(),
            source=self.source.strip(), external_id=self.external_id.strip(),
            revision=self.revision.strip(), quantity=quantity, unit=self.unit.strip(),
            item_code=self.item_code.strip())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self.validate())

@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    action: str
    node_id: str
    user: str = ""
    timestamp: str = ""
    revision: str = ""
    before: Mapping[str, Any] | None = None
    after: Mapping[str, Any] | None = None
    reason: str = ""

    def validate(self) -> "AuditEvent":
        ts = self.timestamp or datetime.now(timezone.utc).isoformat()
        if not self.event_id.strip():
            raise ValueError("event_id is required")
        if not self.action.strip():
            raise ValueError("action is required")
        if not self.node_id.strip():
            raise ValueError("node_id is required")
        return AuditEvent(self.event_id.strip(), self.action.strip(), self.node_id.strip(),
            self.user.strip(), ts, self.revision.strip(),
            dict(self.before or {}), dict(self.after or {}), self.reason.strip())

class AuditTrail:
    def __init__(self, events: Iterable[AuditEvent] = ()):
        self._events: list[AuditEvent] = []
        self._event_ids: set[str] = set()
        for event in events:
            self.append(event)

    def append(self, event: AuditEvent) -> None:
        event = event.validate()
        if event.event_id in self._event_ids:
            raise ValueError(f"duplicate audit event: {event.event_id}")
        self._events.append(event)
        self._event_ids.add(event.event_id)

    def events(self) -> list[dict[str, Any]]:
        return [asdict(x) for x in self._events]

    def export_json(self) -> str:
        return json.dumps(self.events(), ensure_ascii=False, sort_keys=True, indent=2)

    def for_node(self, node_id: str) -> list[dict[str, Any]]:
        return [x for x in self.events() if x["node_id"] == node_id]

class TraceGraph:
    def __init__(self):
        self.nodes: dict[str, TraceNode] = {}
        self.edges: set[tuple[str, str]] = set()

    def add_node(self, node: TraceNode) -> str:
        node = node.validate()
        if node.node_id in self.nodes and self.nodes[node.node_id] != node:
            raise ValueError(f"node id collision: {node.node_id}")
        self.nodes[node.node_id] = node
        return node.node_id

    def link(self, parent: str, child: str) -> None:
        if parent not in self.nodes or child not in self.nodes:
            raise KeyError("both trace nodes must exist before linking")
        self.edges.add((parent, child))

    def lineage(self, node_id: str) -> list[str]:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        parents = {child: set() for child in self.nodes}
        for a, b in self.edges:
            parents.setdefault(b, set()).add(a)
        seen: set[str] = set()
        stack = list(parents.get(node_id, set()))
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(parents.get(current, set()))
        return sorted(seen, key=lambda node: (STAGES.index(self.nodes[node].stage), node))

    def validate(self) -> dict[str, Any]:
        errors = []
        by_external: dict[tuple[str, str], list[str]] = {}
        for node in self.nodes.values():
            if node.external_id:
                key = (node.stage, node.external_id)
                by_external.setdefault(key, []).append(node.node_id)
        duplicates = [ids for ids in by_external.values() if len(ids) > 1]
        for ids in duplicates:
            errors.append({"code": "duplicate_external_id", "node_ids": ids})
        for parent, child in self.edges:
            if self.nodes[parent].stage == self.nodes[child].stage:
                errors.append({"code": "same_stage_edge", "parent": parent, "child": child})
        return {"valid": not errors, "errors": errors, "node_count": len(self.nodes), "edge_count": len(self.edges)}

def build_trace_graph(nodes: Iterable[Mapping[str, Any]], edges: Iterable[tuple[str, str]] = ()) -> TraceGraph:
    graph = TraceGraph()
    for raw in nodes:
        graph.add_node(TraceNode(
            node_id=str(raw.get("node_id") or ""),
            stage=str(raw.get("stage") or ""),
            discipline=str(raw.get("discipline") or ""),
            source=str(raw.get("source") or ""),
            external_id=str(raw.get("external_id") or raw.get("source_id") or ""),
            revision=str(raw.get("revision") or ""),
            quantity=raw.get("quantity"),
            unit=str(raw.get("unit") or ""),
            item_code=str(raw.get("item_code") or raw.get("price_code") or ""),
        ))
    for parent, child in edges:
        graph.link(parent, child)
    return graph

def audit_report(graph: TraceGraph, trail: AuditTrail) -> dict[str, Any]:
    validation = graph.validate()
    return {
        "valid": validation["valid"],
        "validation": validation,
        "nodes": [x.as_dict() for x in graph.nodes.values()],
        "edges": [{"from": a, "to": b} for a, b in sorted(graph.edges)],
        "audit_events": trail.events(),
    }
