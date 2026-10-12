"""Phase 20 — Revision Management orchestration."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from copy import deepcopy

from .engine import RevisionEngine, RevisionResult


@dataclass(frozen=True)
class RevisionSnapshot:
    revision_id: str
    parent_revision_id: str | None
    label: str
    payload: Mapping[str, Any]

@dataclass(frozen=True)
class RevisionManagementResult:
    comparison: RevisionResult
    overlay: tuple[dict[str, Any], ...]
    change_detection: tuple[dict[str, Any], ...]
    impact: dict[str, Any]
    history: tuple[dict[str, Any], ...]

class RevisionManagementWorkflow:
    """Versioned, deterministic and auditable revision workflow."""

    def __init__(self):
        self.engine = RevisionEngine()

    @staticmethod
    def _classify(section: str, change: Mapping[str, Any]) -> str:
        if "added" in change: return "added"
        if "removed" in change: return "removed"
        fields = {str(x.get("field")) for x in change.get("changes", ())}
        quantity_fields = {str(x.get("field")) for x in change.get("quantity_changes", ())}
        if quantity_fields: return "quantity-changed"
        if fields: return "modified"
        return "unchanged"

    def compare(self, old: RevisionSnapshot, new: RevisionSnapshot) -> RevisionManagementResult:
        if new.parent_revision_id != old.revision_id:
            raise ValueError("revision parent does not match compared revision")
        comparison = self.engine.compare(old.payload, new.payload, revision_id=new.revision_id)
        changes = []
        overlay = []
        for section in ("drawing", "elements", "takeoff", "boq"):
            diff = getattr(comparison, section)
            for item in diff["added"]:
                row = {"section": section, "key": item["key"], "status": "added", "before": None, "after": item["after"]}
                changes.append(row); overlay.append(row)
            for item in diff["removed"]:
                row = {"section": section, "key": item["key"], "status": "removed", "before": item["before"], "after": None}
                changes.append(row); overlay.append(row)
            for item in diff["changed"]:
                status = self._classify(section, item)
                row = {"section": section, "key": item["key"], "status": status,
                       "before": {x["field"]: x["before"] for x in item["changes"]},
                       "after": {x["field"]: x["after"] for x in item["changes"]},
                       "quantity_changes": item["quantity_changes"]}
                changes.append(row); overlay.append(row)
        impact = deepcopy(comparison.impact)
        impact["revision_id"] = new.revision_id
        impact["parent_revision_id"] = old.revision_id
        impact["quantity_delta_present"] = any(x.get("quantity_changes") for x in changes)
        impact["affected_sections"] = tuple(sorted({x["section"] for x in changes}))
        history = (
            {"revision_id": old.revision_id, "parent_revision_id": old.parent_revision_id, "label": old.label},
            {"revision_id": new.revision_id, "parent_revision_id": new.parent_revision_id, "label": new.label},
        )
        return RevisionManagementResult(comparison, tuple(overlay), tuple(changes), impact, history)

    @staticmethod
    def snapshot(revision_id: str, payload: Mapping[str, Any], *,
                 label: str = "", parent_revision_id: str | None = None) -> RevisionSnapshot:
        rid = str(revision_id).strip()
        if not rid: raise ValueError("revision_id is required")
        return RevisionSnapshot(rid, parent_revision_id, str(label), deepcopy(dict(payload)))

    @staticmethod
    def export(result: RevisionManagementResult) -> dict[str, Any]:
        return {
            "revision_id": result.comparison.revision_id,
            "overlay": list(result.overlay),
            "change_detection": list(result.change_detection),
            "impact": result.impact,
            "history": list(result.history),
        }
