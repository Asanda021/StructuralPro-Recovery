"""Deterministic technical-office automation for P641-P650.

The automation composes existing drawing/takeoff/BOQ/estimate/report contracts
without inventing engineering values. Every stage preserves source identity and
the final result is reproducible. External AI suggestions remain proposals.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

STAGES = ("drawing", "takeoff", "boq", "estimate", "report")

@dataclass(frozen=True)
class AutomationItem:
    item_id: str
    stage: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    status: str = "ready"

    def validate(self) -> "AutomationItem":
        if self.stage not in STAGES:
            raise ValueError("invalid automation stage")
        if not self.item_id.strip() or not self.source_ids:
            raise ValueError("automation identity and provenance are required")
        if self.status not in {"ready", "review", "approved", "blocked"}:
            raise ValueError("invalid automation status")
        return self

@dataclass(frozen=True)
class AutomationPlan:
    project_id: str
    items: tuple[AutomationItem, ...]
    review_required: tuple[str, ...]
    fingerprint: str

    def validate(self) -> "AutomationPlan":
        if not self.project_id.strip():
            raise ValueError("project_id is required")
        if not self.items:
            raise ValueError("automation plan cannot be empty")
        if not self.fingerprint:
            raise ValueError("fingerprint is required")
        for item in self.items:
            item.validate()
        return self

def _fingerprint(project_id: str, items: Sequence[AutomationItem]) -> str:
    payload = [{
        "item_id": x.item_id, "stage": x.stage, "source_ids": list(x.source_ids),
        "payload": dict(x.payload), "status": x.status
    } for x in sorted(items, key=lambda v: v.item_id)]
    raw = json.dumps({"project_id": project_id, "items": payload},
                     ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()

def build_plan(project_id: str, stages: Mapping[str, Sequence[Mapping[str, Any]]]) -> AutomationPlan:
    """Build a deterministic plan; missing stages stay empty, but no data is invented."""
    items: list[AutomationItem] = []
    for stage in STAGES:
        for row in stages.get(stage, ()):
            source = str(row.get("source_id", "")).strip()
            item_id = str(row.get("item_id", "")).strip()
            if not source or not item_id:
                raise ValueError(f"{stage} item requires item_id and source_id")
            status = "review" if row.get("requires_review", False) else "ready"
            items.append(AutomationItem(item_id, stage, (source,), dict(row), status))
    if not items:
        raise ValueError("no source-backed automation items")
    review = tuple(sorted(x.item_id for x in items if x.status == "review"))
    fp = _fingerprint(project_id, items)
    return AutomationPlan(project_id, tuple(sorted(items, key=lambda x: (STAGES.index(x.stage), x.item_id))),
                          review, fp).validate()

def advance(plan: AutomationPlan, approvals: Mapping[str, bool]) -> AutomationPlan:
    """Approve only explicitly reviewed items; unapproved items remain blocked."""
    updated = []
    for item in plan.items:
        if item.status != "review":
            updated.append(item)
            continue
        if approvals.get(item.item_id) is True:
            updated.append(AutomationItem(item.item_id, item.stage, item.source_ids,
                                          item.payload, "approved"))
        else:
            updated.append(AutomationItem(item.item_id, item.stage, item.source_ids,
                                          item.payload, "blocked"))
    fp = _fingerprint(plan.project_id, updated)
    return AutomationPlan(plan.project_id, tuple(updated),
                          tuple(sorted(x.item_id for x in updated if x.status in {"review","blocked"})),
                          fp).validate()
