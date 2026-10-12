"""Professional manual takeoff session: explicit inputs, deterministic quantities, traceability.

This module is a domain layer, not a UI replacement. It never silently fills missing
geometry: project defaults apply only when the caller explicitly confirms each field.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Mapping

from core.takeoff.engine import TakeoffEngine, TakeoffRow
from core.takeoff.manual_input import ManualEntry, parse_manual_batch, parse_manual_entry

_CODE_TO_ENGINE = {
    "column": ("building", "column"), "beam": ("building", "beam"),
    "tie_beam": ("building", "tie_beam"), "footing_concrete": ("advanced", "footing_concrete"),
    "shear_wall": ("building", "shear_wall"), "solid_slab_roof": ("building", "solid_slab_roof"),
    "joist_block_roof": ("building", "joist_block_roof"), "joist_foam_roof": ("building", "joist_foam_roof"),
    "stair_concrete": ("building", "stair_concrete"), "wall": ("building", "wall"),
    "excavation": ("civil", "excavation"), "rebar": ("building", "rebar"), "steel": ("advanced", "steel"),
}

@dataclass(frozen=True)
class ManualTakeoffDraft:
    project_id: str
    floor_id: str
    entry: ManualEntry
    missing: tuple[str, ...]
    message: str = "برای محاسبه، ورودی‌های مشخص‌شده را تکمیل کنید."

@dataclass(frozen=True)
class ManualTakeoffRecord:
    record_id: str
    project_id: str
    floor_id: str
    element_label: str
    code: str
    params: Mapping[str, float]
    quantity: float
    unit: str
    formula: str
    source: str
    revision: int = 1
    status: str = "draft"

    def to_dict(self) -> dict:
        result = asdict(self)
        result["params"] = dict(self.params)
        return result

class ManualTakeoffWorkbench:
    """Project/floor-aware manual takeoff register with explicit defaults and undo/redo."""
    def __init__(self, project_id: str, *, project_defaults: Mapping[str, float] | None = None, engine: TakeoffEngine | None = None):
        if not str(project_id).strip(): raise ValueError("project_id is required")
        self.project_id = str(project_id).strip()
        self.project_defaults = dict(project_defaults or {})
        self.engine = engine or TakeoffEngine()
        self._records: list[ManualTakeoffRecord] = []
        self._undo: list[tuple[ManualTakeoffRecord, ...]] = []
        self._redo: list[tuple[ManualTakeoffRecord, ...]] = []
        self._next_id = 1

    @property
    def records(self) -> tuple[ManualTakeoffRecord, ...]: return tuple(self._records)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_preview(self) -> tuple[ManualTakeoffRecord, ...]:
        """Read-only target state for UI safety checks before undo."""
        return self._undo[-1] if self._undo else self.records

    def _snapshot(self) -> None:
        self._undo.append(tuple(self._records))
        self._redo.clear()

    def add_text(self, text: str, *, floor_id: str, element_label: str = "", confirmed_default_fields: tuple[str, ...] = ()) -> ManualTakeoffRecord | ManualTakeoffDraft:
        if not str(floor_id).strip(): raise ValueError("floor_id is required")
        entry = parse_manual_entry(text)
        params = dict(entry.params)
        for field in set(confirmed_default_fields):
            if field not in params and field in self.project_defaults: params[field] = float(self.project_defaults[field])
        fields = {
            "column": ("count", "width", "depth", "height"), "beam": ("count", "length", "width", "depth"),
            "tie_beam": ("count", "length", "width", "depth"), "footing_concrete": ("count", "length", "width", "thickness"),
            "shear_wall": ("count", "length", "thickness", "height"), "solid_slab_roof": ("count", "length", "width", "thickness"),
            "joist_block_roof": ("count", "length", "width", "topping_thickness", "joist_spacing", "joist_width", "joist_depth"),
            "joist_foam_roof": ("count", "length", "width", "topping_thickness", "joist_spacing", "joist_width", "joist_depth"),
            "stair_concrete": ("count", "sloped_length", "width", "waist_thickness"), "wall": ("count", "length", "height", "openings"),
            "excavation": ("length", "width", "depth"), "rebar": ("count", "length", "unit_weight"), "steel": ("count", "length", "unit_weight"),
        }.get(entry.code, ())
        missing = tuple(k for k in fields if k not in params or (params[k] < 0 if k == "openings" else params[k] <= 0))
        if missing:
            updated = ManualEntry(entry.code, params, missing, entry.source_text)
            return ManualTakeoffDraft(self.project_id, str(floor_id).strip(), updated, missing)
        if entry.code not in _CODE_TO_ENGINE: raise ValueError(f"manual takeoff mapping is not available for: {entry.code}")
        domain, item = _CODE_TO_ENGINE[entry.code]
        row: TakeoffRow = self.engine.calculate(domain, item, description=element_label or entry.code, source="manual", **params)
        self._snapshot()
        record = ManualTakeoffRecord(f"MT-{self._next_id:06d}", self.project_id, str(floor_id).strip(), element_label or entry.code, entry.code, dict(params), row.quantity, row.unit, row.formula, entry.source_text)
        self._next_id += 1
        self._records.append(record)
        return record

    def add_batch(self, text: str, *, floor_id: str) -> tuple[ManualTakeoffRecord | ManualTakeoffDraft, ...]:
        previous = (list(self._records), list(self._undo), list(self._redo), self._next_id)
        try:
            return tuple(self.add_text(entry.source_text, floor_id=floor_id) for entry in parse_manual_batch(text))
        except Exception:
            self._records, self._undo, self._redo, self._next_id = previous
            raise

    def undo(self) -> tuple[ManualTakeoffRecord, ...]:
        if self._undo: self._redo.append(tuple(self._records)); self._records = list(self._undo.pop())
        return self.records

    def redo(self) -> tuple[ManualTakeoffRecord, ...]:
        if self._redo: self._undo.append(tuple(self._records)); self._records = list(self._redo.pop())
        return self.records

    def remove_record(self, record_id: str) -> tuple[ManualTakeoffRecord, ...]:
        """Remove one pending record with undo/redo support."""
        key = str(record_id or "").strip()
        index = next((i for i, row in enumerate(self._records) if row.record_id == key), None)
        if index is None:
            raise KeyError(f"manual takeoff record not found: {key}")
        self._snapshot()
        self._records.pop(index)
        return self.records

    def export_rows(self) -> tuple[dict, ...]: return tuple(record.to_dict() for record in self._records)
