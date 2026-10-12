import json
from pathlib import Path

import pytest

from core.takeoff.construction_core import ConstructionQuantityCore
from core.takeoff.element_model import ConstructionElement
from core.takeoff.estimate import build_estimate
from core.validation.golden import GoldenCase, validate_case


FIXTURE=Path("validation/golden_cases/GOLDEN-STRUCTURAL-CORE-002.json")


def test_representative_structural_fixture_matches_authoritative_engines():
    payload=json.loads(FIXTURE.read_text(encoding="utf-8"))
    case=GoldenCase(**payload)

    column=ConstructionElement("COL-1","column",length_m=0.3,width_m=0.3,height_m=3.0,quantity_count=4,source_id="golden:COL-1")
    slab=ConstructionElement("SLAB-1","slab",area_m2=120.0,thickness_m=0.15,quantity_count=1,source_id="golden:SLAB-1")
    lines=[
        ConstructionQuantityCore.rectangular_volume(column),
        ConstructionQuantityCore.slab_volume(slab),
        ConstructionQuantityCore.rebar_weight("RB-1",12.0,16.0,100,source_id="golden:RB-1"),
    ]
    estimate=build_estimate(lines, aggregate=True)
    quantities=[{"object_id":x.element_id,"item_code":x.item_code,"quantity":x.quantity,"unit":x.unit} for x in lines]
    boq=[{"item_code":x["item_code"],"quantity":x["quantity"],"unit":x["unit"]} for x in estimate["boq"]]
    result=validate_case(case, quantities, boq)
    assert result.passed, result.issues


def test_representative_fixture_is_stable_and_nonempty():
    payload=json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["case_id"].startswith("GOLDEN-")
    assert payload["expected_quantities"]
    assert payload["expected_boq"]
    assert len(payload["tolerances"]) > 0
