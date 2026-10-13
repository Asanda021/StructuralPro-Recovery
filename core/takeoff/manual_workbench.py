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
    params: Mapping[str, float | str]
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

    @property
    def redo_preview(self):
        return self._redo[-1] if self._redo else self.records

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
            "joist_block_roof": ("count", "length", "width", "topping_thickness", "joist_spacing", "joist_width", "joist_depth","joist_count"),
            "joist_foam_roof": ("count", "length", "width", "topping_thickness", "joist_spacing", "joist_width", "joist_depth","joist_count"),
            "stair_concrete": ("count", "sloped_length", "width", "waist_thickness"), "wall": ("count", "length", "height", "openings"),
            "excavation": ("length", "width", "depth"), "rebar": ("count", "length", "unit_weight"), "steel": ("count", "length", "unit_weight"),
        }.get(entry.code, ())
        missing = tuple(k for k in fields if k not in params or (params[k] < 0 if k == "openings" else params[k] <= 0))
        missing += tuple(k for k in entry.missing if k not in fields)
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

    def _selected(self, ids):
        ids=list(ids)
        if not ids or len(ids)!=len(set(ids)):raise ValueError('شناسه ردیف‌ها باید صریح و یکتا باشد')
        lookup={r.record_id:r for r in self._records}
        if any(key not in lookup for key in ids):raise KeyError('ردیف انتخابی وجود ندارد')
        return [lookup[key] for key in ids]

    def remove_records(self, ids):
        rows=self._selected(ids);keys={r.record_id for r in rows};self._snapshot()
        self._records=[r for r in self._records if r.record_id not in keys]
        return self.records

    def copy_records(self, ids, *, floor_id):
        rows=self._selected(ids)
        if not str(floor_id).strip():raise ValueError('طبقه مقصد باید صریح باشد')
        if any(r.floor_id==str(floor_id).strip() for r in rows):raise ValueError('کپی همان منبع در همان طبقه نیازمند هویت فیزیکی مستقل است')
        previous=(list(self._records),list(self._undo),list(self._redo),self._next_id)
        try:
            copies=[self.add_text(r.source,floor_id=floor_id,element_label=r.element_label) for r in rows]
            if any(isinstance(r,ManualTakeoffDraft) for r in copies):raise ValueError('کپی ردیف ناقص مجاز نیست')
            self._undo=previous[1]+[tuple(previous[0])];self._redo=[]
            return tuple(copies)
        except Exception:
            self._records,self._undo,self._redo,self._next_id=previous
            raise

    def update_text(self, record_id, text, *, expected_revision, floor_id=None, element_label=None):
        from dataclasses import replace
        old=self._selected([record_id])[0]
        if isinstance(expected_revision,bool) or not isinstance(expected_revision,int) or expected_revision!=old.revision:raise RuntimeError('نسخه ردیف تغییر کرده است')
        previous=(list(self._records),list(self._undo),list(self._redo),self._next_id)
        try:
            result=self.add_text(text,floor_id=floor_id or old.floor_id,element_label=old.element_label if element_label is None else element_label)
            if isinstance(result,ManualTakeoffDraft):raise ValueError('داده ویرایش‌شده ناقص است؛ ردیف قبلی حفظ شد')
            result=replace(result,record_id=old.record_id,revision=old.revision+1)
        finally:self._records,self._undo,self._redo,self._next_id=previous
        self._snapshot();self._records=[result if r.record_id==record_id else r for r in self._records]
        return result
