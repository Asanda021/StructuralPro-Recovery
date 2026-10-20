"""Bounded cement-render NET SURFACE takeoff against existing actual AEC services.

All measurements are explicit synthetic examples, not approved drawings or
whole-family professional acceptance. No assumptions about layer thickness,
waste, substrate, finishing requirements, or other assembly components.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system


# Physical dimensions in metres; openings_m2 is an explicit TOTAL deduction
# from count * length * height, not a guessed per-face allowance.
EXPLICIT = (
    ("4.8", "2.75", "2", "1.25", "25.15"),
    ("1.25", "2.25", "3", "0.375", "8.0625"),
    ("3.75", "1.2", "2", "0", "9"),
)


def independent_net_area(length, height, count, openings):
    return (Decimal(length) * Decimal(height) * Decimal(count)
            - Decimal(openings))


def document(length="4.8", height="2.75", count="2", openings="1.25"):
    assert SPECS["cement_render"].essential == ("render_coat",)
    draft = empty_system("cement_render", "L1", "WALL-RENDER-1")
    draft["source"] = {
        "mode": "manual",
        "source_id": "SYNTHETIC:RENDER:SPECIFIED-SURFACE:1",
    }
    for name in SPECS["cement_render"].components:
        draft["components"][name] = {
            "status": "not_applicable",
            "reason": "Excluded only from this synthetic render-coat component test",
            "source_ref": "SYNTHETIC-REVIEW-SCOPE",
            "approved_by": "SYNTHETIC-TEST-REVIEWER",
        }
    draft["components"]["render_coat"] = {
        "status": "confirmed",
        "approved_by": "SYNTHETIC-TEST-REVIEWER",
        "items": [{
            "line_id": "SURFACE-1",
            "source_ref": "SYNTHETIC-FACE-1",
            "description": "Synthetic documented render surface",
            "domain": "building",
            "item_code": "SYNTHETIC-RENDER",
            "mode": "detail",
            "detail_type": "net_surface",
            "details": {"entries": [{
                "id": "WALL-FACE-1",
                "source_ref": "SYNTHETIC-FACE-DIMENSIONS-1",
                "approved_by": "SYNTHETIC-TEST-REVIEWER",
                "count": count, "length_m": length, "width_m": height,
                "openings_m2": openings,
            }]},
        }],
    }
    return draft


@pytest.mark.parametrize("length,height,count,openings,expected", EXPLICIT)
def test_cement_render_net_surface_matches_independent_decimal_oracle(
        length, height, count, openings, expected):
    assert independent_net_area(length, height, count, openings) == Decimal(expected)
    draft = document(length, height, count, openings)
    unchanged = deepcopy(draft)
    outcome = preview_system(draft, TakeoffEngine())
    assert outcome["ready"], outcome["blockers"]
    assert outcome["preview_only"]
    row, = outcome["rows"]
    assert row["component"] == "render_coat"
    assert row["unit"] == "m2"
    assert row["method"] == "detail"
    assert row["formula"] == "جمع سطوح خالص واقعی پس از کسورات بازشو"
    assert abs(Decimal(str(row["quantity"])) - Decimal(expected)) < Decimal("1e-12")
    assert draft == unchanged


@pytest.mark.parametrize("tamper", (
    "missing_source", "missing_reviewer", "duplicate_physical_face",
    "zero_count", "negative_opening", "too_large_opening",
    "missing_opening_field", "wrong_discipline", "duplicate_line",
    "unreviewed_component",
))
def test_invalid_cement_render_inputs_clear_all_preview_rows(tamper):
    draft = document()
    group = draft["components"]["render_coat"]
    item = group["items"][0]
    detail = item["details"]["entries"][0]
    if tamper == "missing_source":
        draft["source"] = {}
    elif tamper == "missing_reviewer":
        detail["approved_by"] = ""
    elif tamper == "duplicate_physical_face":
        item["details"]["entries"].append(deepcopy(detail))
    elif tamper == "zero_count":
        detail["count"] = "0"
    elif tamper == "negative_opening":
        detail["openings_m2"] = "-1"
    elif tamper == "too_large_opening":
        detail["openings_m2"] = "100"
    elif tamper == "missing_opening_field":
        del detail["openings_m2"]
    elif tamper == "wrong_discipline":
        item["domain"] = "electrical"
    elif tamper == "duplicate_line":
        group["items"].append(deepcopy(item))
    elif tamper == "unreviewed_component":
        group["status"] = "unreviewed"
    outcome = preview_system(draft, TakeoffEngine())
    assert not outcome["ready"]
    assert outcome["blockers"]
    assert outcome["rows"] == []


def test_cement_render_geometry_change_never_reuses_prior_expected_quantity():
    old = independent_net_area("4.8", "2.75", "2", "1.25")
    amended = preview_system(document("4.8", "2.75", "2", "1.5"), TakeoffEngine())
    assert amended["ready"], amended["blockers"]
    new_value = Decimal(str(amended["rows"][0]["quantity"]))
    assert abs(new_value - old) > Decimal("1e-12")
    assert abs(new_value - independent_net_area("4.8", "2.75", "2", "1.5")) < Decimal("1e-12")


def test_sqlite_save_reopen_stale_cas_preserves_existing_nonempty_boq(tmp_path):
    directory = tmp_path / "cement-render"
    app = StructuralProApp(directory)
    draft = document("1.25", "2.25", "3", "0.375")
    try:
        app.create_project("آزمون مصنوعی اندود سیمانی", "P")
        app.add_takeoff(
            "P", "building", "column",
            source_id="SYNTHETIC:UNRELATED:BOQ",
            system="OTHER", manual_location_id="COLUMN-1",
            count=1, width=0.4, depth=0.4, height=3,
        )
        original = app.open_project("P")
        assert original["boq"] and original["takeoffs"]
        saved = app.save_aec_system_draft("P", draft, expected_revision=0)
        assert saved["revision"] == 1 and saved["status"] == "draft"
        before = deepcopy(app.open_project("P"))
        digest = app.store.current_digest("P")
        with pytest.raises(RuntimeError):
            app.save_aec_system_draft("P", draft, expected_revision=0)
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == before
    finally:
        app.store.close()

    reopened = StructuralProApp(directory)
    try:
        current = reopened.get_aec_system("P", "cement_render", "L1", "WALL-RENDER-1")
        assert current["revision"] == 1
        assert current["data"] == draft
        outcome = reopened.preview_aec_system("P", "cement_render", "L1", "WALL-RENDER-1")
        assert outcome["ready"], outcome["blockers"]
        line, = outcome["rows"]
        assert line["unit"] == "m2"
        assert abs(Decimal(str(line["quantity"])) - Decimal("8.0625")) < Decimal("1e-12")
        for field in ("takeoffs", "boq"):
            assert reopened.open_project("P")[field] == original[field]
        assert reopened.store.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        reopened.store.close()
