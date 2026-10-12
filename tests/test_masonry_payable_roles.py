"""Regression: independent masonry material evidence is not a second payable work item."""

from copy import deepcopy

import pytest

from core.platform.application import StructuralProApp


INPUTS = {
    "length": 10, "height": 3, "thickness": 0.20, "openings": 0,
    "block_length": 0.39, "block_height": 0.19, "block_thickness": 0.19,
    "joint_thickness": 0.01, "cement_parts": 1, "sand_parts": 4,
}


def _legacy_row(code, *, unit_price=None, role=None):
    row = {
        "source_id": f"masonry-legacy:{code}", "domain": "assembly", "system": "L1",
        "params": {"assembly_code": "block_wall"},
        "quantities": [{
            "code": code, "title": code, "unit": "m²" if code == "wall_area" else "m³",
            "amount": 10, "price_code": "PR" if unit_price is not None else None,
            "unit_price": unit_price,
        }],
    }
    if role is not None:
        row["component_role"] = role
        row["quantities"][0]["role"] = role
    return row


def test_block_wall_bills_work_once_and_persists_other_components_as_evidence(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("آزمون دیوار", "masonry-p1")
    result = app.add_assembly_takeoff(
        "masonry-p1", "block_wall", INPUTS,
        floor_id="طبقه ۱", location_id="W-001",
        component_prices={"wall_area": {"price_code": "M-01", "unit": "m²", "unit_price": 100}},
    )
    roles = {row["item"]: row["component_role"] for row in result["rows"]}
    assert roles == {
        "wall_area": "work", "block": "procurement", "mortar": "material",
        "cement": "material", "sand": "material",
    }
    project = app.open_project("masonry-p1")
    assert len(project["takeoffs"]) == 5
    assert len(project["boq"]) == 1
    assert project["boq"][0]["item_code"] == "wall_area"
    assert project["boq"][0]["quantity"] == pytest.approx(30)
    app.store.close()
    reopened = StructuralProApp(tmp_path).open_project("masonry-p1")
    assert len(reopened["takeoffs"]) == 5
    assert len(reopened["boq"]) == 1


@pytest.mark.parametrize("material", ["block", "mortar", "cement", "sand"])
def test_block_wall_rejects_pricing_material_evidence_before_sqlite_write(tmp_path, material):
    app = StructuralProApp(tmp_path)
    app.create_project("آزمون مصالح", "masonry-p2")
    with pytest.raises(ValueError, match="اجزای تأمین و مصرف"):
        app.add_assembly_takeoff(
            "masonry-p2", "block_wall", INPUTS, floor_id="L1", location_id="W-001",
            component_prices={material: {"price_code": "M-EXTRA", "unit": "m³" if material != "block" else "عدد", "unit_price": 5}},
        )
    project = app.open_project("masonry-p2")
    assert project["takeoffs"] == []
    assert project["boq"] == []


def test_unpriced_legacy_masonry_evidence_is_filtered_without_deleting_rows(tmp_path):
    app = StructuralProApp(tmp_path)
    project = {"takeoffs": [_legacy_row(x) for x in ("wall_area", "block", "mortar", "cement", "sand")], "boq": []}
    project["takeoffs"][0]["quantities"][0].update(price_code="WORK", unit_price=50)
    original = deepcopy(project)
    boq = app._build_project_boq(project)
    assert len(boq) == 1
    assert boq[0]["item_code"] == "wall_area"
    assert project == original


def test_priced_legacy_masonry_material_requires_review_instead_of_silent_reclassification(tmp_path):
    app = StructuralProApp(tmp_path)
    project = {"takeoffs": [_legacy_row("wall_area"), _legacy_row("cement", unit_price=5)], "boq": []}
    with pytest.raises(ValueError, match="بازبینی"):
        app._build_project_boq(project)


def test_explicit_incorrect_work_role_cannot_force_payment_for_masonry_material(tmp_path):
    app = StructuralProApp(tmp_path)
    project = {"takeoffs": [_legacy_row("block", role="work")], "boq": []}
    with pytest.raises(ValueError, match="نقش"):
        app._build_project_boq(project)
