"""Bounded independent blinding-concrete volume oracle against REAL AEC services.

Explicitly synthetic rectangular FOOTPRINT input, not an approved shop drawing.
This does NOT close the full blinding_concrete family: base preparation, edge
formwork, irregular shapes, deductions and independent engineer signoff remain
subject to genuine project-specific review. No payable BOQ mutation is allowed.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system


# Distinct exact-decimal references: never derived from TakeoffEngine results.
# Each (length_m, width_m, thickness_m, count, expected_m3) is EXPLICIT synthetic input.
CASES = [
    ("3", "2", "0.1", "1", "0.6"),
    ("2.4", "1.25", "0.08", "4", "0.960"),
    ("1.125", "2.25", "0.15", "2", "0.759375"),
]


def _independent_volume(length, width, thickness, count):
    """Independent dimension product; no product engine or rounding shortcut."""
    return Decimal(length) * Decimal(width) * Decimal(thickness) * Decimal(count)


def _document(dimensions):
    assert SPECS["blinding_concrete"].essential == ("blinding_concrete",)
    length, width, thickness, count = dimensions
    doc = empty_system("blinding_concrete", "L1", "BLINDING-SYN-1")
    doc["source"] = {"mode": "manual", "source_id": "SYNTHETIC-DRAWING:BLINDING:1"}
    # Explicit synthetic review decisions, not names of licensed engineers.
    for component in SPECS["blinding_concrete"].components:
        doc["components"][component] = {
            "status": "not_applicable",
            "reason": "Out of scope for synthetic rectangular volume-only calculation",
            "source_ref": "SYNTHETIC-REVIEW-BOUNDARY",
            "approved_by": "SYNTHETIC-TEST-REVIEWER-NOT-AN-ENGINEER",
        }
    doc["components"]["blinding_concrete"] = {
        "status": "confirmed",
        "approved_by": "SYNTHETIC-TEST-REVIEWER-NOT-AN-ENGINEER",
        "items": [{
            "line_id": "RECT-1",
            "source_ref": "SYNTHETIC-RECTANGLE-1",
            "description": "Synthetic rectangular blinding-concrete footprint",
            "domain": "advanced",
            "item_code": "SYNTHETIC-BLINDING",
            "mode": "engine",
            "item": "footing_concrete",
            "params": {
                "length": length, "width": width, "thickness": thickness,
                "count": count,
            },
        }],
    }
    return doc


def _preview(doc):
    return preview_system(doc, TakeoffEngine())


@pytest.mark.parametrize("length,width,thickness,count,expected", CASES)
def test_independent_decimal_volume_matches_real_reviewed_aec_preview(
    length, width, thickness, count, expected
):
    values = (length, width, thickness, count)
    assert _independent_volume(*values) == Decimal(expected)
    doc = _document(values)
    original = deepcopy(doc)
    result = _preview(doc)
    assert result["ready"], result["blockers"]
    assert result["preview_only"] is True
    row, = result["rows"]
    assert row["component"] == "blinding_concrete"
    assert row["unit"] == "m3"
    assert row["domain"] == "advanced"
    assert row["source_id"].startswith("aec:blinding_concrete:L1:BLINDING-SYN-1:")
    actual = Decimal(str(row["quantity"]))
    assert abs(actual - Decimal(expected)) < Decimal("1e-12")
    assert doc == original


@pytest.mark.parametrize("tamper", [
    "missing_length", "zero_thickness", "negative_width",
    "extra_unsupported_dimension", "no_source", "no_reviewer",
    "wrong_discipline", "duplicate_line", "not_reviewed",
])
def test_invalid_or_unreviewed_blinding_quantity_fails_closed(tamper):
    doc = _document(("3", "2", "0.1", "1"))
    comp = doc["components"]["blinding_concrete"]
    line = comp["items"][0]
    if tamper == "missing_length":
        del line["params"]["length"]
    elif tamper == "zero_thickness":
        line["params"]["thickness"] = "0"
    elif tamper == "negative_width":
        line["params"]["width"] = "-2"
    elif tamper == "extra_unsupported_dimension":
        line["params"]["openings"] = "1"
    elif tamper == "no_source":
        doc["source"] = {}
    elif tamper == "no_reviewer":
        comp["approved_by"] = ""
    elif tamper == "wrong_discipline":
        line["domain"] = "civil"
    elif tamper == "duplicate_line":
        comp["items"].append(deepcopy(line))
    elif tamper == "not_reviewed":
        comp["status"] = "unreviewed"
    result = _preview(doc)
    assert not result["ready"]
    assert result["rows"] == []
    assert result["blockers"]


def test_wrong_physical_unit_cannot_launder_synthetic_volume_to_mass():
    doc = _document(("3", "2", "0.1", "1"))
    item = doc["components"]["blinding_concrete"]["items"][0]
    item.update(mode="measured", quantity="0.6", unit="kg",
                formula="Unapproved substitute", measurement_ref="SYNTHETIC-SWAP")
    item.pop("item")
    item.pop("params")
    result = _preview(doc)
    assert not result["ready"] and result["rows"] == []


def test_independent_oracle_detects_changed_but_valid_geometry():
    """A new legitimate dimension requires a NEW expected quantity, not old acceptance."""
    old = _independent_volume("3", "2", "0.1", "1")
    changed_doc = _document(("3", "2", "0.11", "1"))
    changed = _preview(changed_doc)
    assert changed["ready"], changed["blockers"]
    actual = Decimal(str(changed["rows"][0]["quantity"]))
    assert abs(actual - old) > Decimal("1e-12")
    assert abs(actual - _independent_volume("3", "2", "0.11", "1")) < Decimal("1e-12")


def test_real_sqlite_reopen_cas_and_existing_payable_boq_never_touched(tmp_path):
    path = tmp_path / "projects.db"
    app = StructuralProApp(path)
    doc = _document(("2.4", "1.25", "0.08", "4"))
    try:
        app.create_project("پروژه آزمایشی بتن مگر", "P")
        app.add_takeoff("P", "building", "column",
                        source_id="SYNTHETIC-UNRELATED-BOQ-ROW",
                        system="OTHER", manual_location_id="COLUMN-1",
                        count=1, width=0.4, depth=0.4, height=3)
        prior = app.open_project("P")
        assert prior["boq"] and prior["takeoffs"]
        saved = app.save_aec_system_draft("P", doc, expected_revision=0)
        assert saved["status"] == "draft" and saved["revision"] == 1
        immutable = deepcopy(app.open_project("P"))
        digest = app.store.current_digest("P")
        with pytest.raises(RuntimeError):
            app.save_aec_system_draft("P", doc, expected_revision=0)
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == immutable
    finally:
        app.store.close()

    reopened = StructuralProApp(path)
    try:
        loaded = reopened.get_aec_system("P", "blinding_concrete", "L1", "BLINDING-SYN-1")
        assert loaded["data"] == doc and loaded["revision"] == 1
        outcome = reopened.preview_aec_system("P", "blinding_concrete", "L1", "BLINDING-SYN-1")
        assert outcome["ready"], outcome["blockers"]
        row, = outcome["rows"]
        assert abs(Decimal(str(row["quantity"])) - Decimal("0.960")) < Decimal("1e-12")
        assert row["unit"] == "m3"
        for field in ("boq", "takeoffs"):
            assert reopened.open_project("P")[field] == prior[field]
        assert reopened.store.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        reopened.store.close()
