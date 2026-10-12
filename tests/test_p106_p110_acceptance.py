import json
from pathlib import Path
from core.acceptance.p106_p110 import load_cases,run_engineering_case,run_dwg_boundary,run_bim_roundtrip,run_e2e

ROOT=Path(__file__).parents[1]

def test_p106_representative_real_project_pack():
    cases=load_cases(ROOT/"validation/acceptance_cases")
    assert len(cases)>=5
    for case in cases:
        r=run_engineering_case(case)
        assert r["concrete_m3"]==case["expected"]["concrete_m3"]
        assert abs(r["rebar_kg"]-case["expected"]["rebar_kg"])<1e-9
        assert r["stock_bars"]==case["expected"]["stock_bars"]

def test_p107_engineering_depth_cases_are_deterministic():
    cases=load_cases(ROOT/"validation/acceptance_cases")
    first=[run_engineering_case(x) for x in cases]
    second=[run_engineering_case(x) for x in cases]
    assert first==second

def test_p108_dwg_boundary_is_transparent():
    result=run_dwg_boundary()
    assert isinstance(result["available"],bool)
    assert result["message"]
    if result["available"]:
        assert result["converter"] or result["native_reader"]

def test_p109_bim_roundtrip_integrity():
    model={"sources":[{"id":"S1","format":"IFC","revision":"R1"}],
           "objects":[{"object_id":"C1","type":"column","level":"L1","quantity":2.5}]}
    result=run_bim_roundtrip(model)
    assert result["verified"] and result["digest"]

def test_p110_end_to_end_takeoff_boq_estimate():
    cases=load_cases(ROOT/"validation/acceptance_cases")
    for case in cases:
        result=run_e2e(case)
        assert result["ready"] is True
        assert result["validation"]["valid"] is True
        assert result["totals"]["amount"]>0

def test_acceptance_fixture_schema():
    for path in sorted((ROOT/"validation/acceptance_cases").glob("P106-*.json")):
        data=json.loads(path.read_text(encoding="utf-8"))
        assert {"case_id","name","geometry","rebar","cut_lengths_m","unit_price","expected"}<=data.keys()
