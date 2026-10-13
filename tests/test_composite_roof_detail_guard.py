"""No full corrugated-deck concrete quantity from a bounding rectangle."""
from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp

TOPPING = {
    "composite_scope": "topping_only", "deck_profile_ref": "synthetic:deck-profile:C1",
    "reviewed_concrete_regions": {"entries": [
        {"id": "bay-1", "source_ref": "synthetic:sheet:C1:bay-1", "approved_by": "reviewer-A",
         "length_m": 4, "width_m": 3, "thickness_m": 0.2, "voids": []},
    ]},
}

@pytest.mark.parametrize("params", [
    {"length": 4, "width": 3, "thickness": .2, "count": 1},
    {},
    {**TOPPING, "count": 1},
    {**TOPPING, "composite_scope": "complete_roof"},
    {**TOPPING, "deck_profile_ref": ""},
    {**TOPPING, "reviewed_concrete_regions": {"entries": []}},
])
def test_composite_rejects_inferred_full_roof_or_unreviewed_input(tmp_path, params):
    app = StructuralProApp(tmp_path)
    app.create_project("سقف مرکب", "p")
    before = app.open_project("p")
    with pytest.raises((ValueError, KeyError)):
        app.add_takeoff("p", "building", "steel_roof_composite_concrete",
                        source_id="synthetic:composite:C1", **params)
    assert app.open_project("p") == before
    app.store.close()

def test_topping_only_keeps_real_provenance_without_guessing_troughs(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("سقف مرکب", "p")
    row = app.add_takeoff("p", "building", "steel_roof_composite_concrete",
                          source_id="synthetic:composite:C1", system="L1", **deepcopy(TOPPING))
    assert row["quantities"][0]["amount"] == pytest.approx(2.4)
    assert "فقط" in row["quantities"][0]["warning"]
    assert row["params"]["reviewed_concrete_regions"]["entries"][0]["source_ref"]
    app.store.close()
    reopened = StructuralProApp(tmp_path)
    assert reopened.open_project("p")["boq"][0]["quantity"] == pytest.approx(2.4)
    reopened.store.close()

def test_duplicate_or_unreviewed_concrete_region_is_blocked(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("سقف مرکب", "p")
    for modifier in ("repeat_id", "no_reviewer", "unverified_void"):
        payload = deepcopy(TOPPING)
        entries = payload["reviewed_concrete_regions"]["entries"]
        if modifier == "repeat_id": entries.append(deepcopy(entries[0]))
        if modifier == "no_reviewer": entries[0]["approved_by"] = ""
        if modifier == "unverified_void":
            entries[0]["voids"] = [{"id":"V1","volume_m3":0.1,"source_ref":"ref","approved_by":"reviewer"}]
        with pytest.raises(ValueError):
            app.add_takeoff("p", "building", "steel_roof_composite_concrete",
                            source_id=f"synthetic:{modifier}", **payload)
    assert app.open_project("p")["boq"] == []
    app.store.close()
