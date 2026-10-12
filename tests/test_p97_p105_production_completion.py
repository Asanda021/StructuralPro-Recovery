import json
from pathlib import Path

def test_p97_deep_quantity_rules():
    from core.engineering.deep_quantity import rebar_unit_weight, bar_cut_plan, roof_concrete_volume
    assert round(rebar_unit_weight(16),3)==round(256/162,3)
    plan=bar_cut_plan([5,4,3,2,1],12)
    assert plan["stock_bar_count"]==2
    assert abs(roof_concrete_volume(100,0.2,"joist_single")-3.6)<1e-9

def test_p98_edit_review_freeze():
    from core.drawings.production_workflow import ProductionDrawing
    d=ProductionDrawing([{"object_id":"B1","length":5}],"S1")
    d.classify(lambda x:"beam")
    d.enable_editing(); d.edit("B1",{"length":6},"user")
    d.review({"B1":True}); d.freeze()
    assert d.state=="frozen" and d.digest()

def test_p99_roundtrip_manifest_is_lossless():
    from core.bim.roundtrip import roundtrip_manifest, verify_manifest
    sample={"sources":[{"id":"S1"}],"objects":[{"id":"B1","type":"beam","properties":{"length":5}}]}
    m=roundtrip_manifest(sample)
    assert verify_manifest(m)
    m["registry"]["objects"][0]["properties"]["length"]=6
    assert not verify_manifest(m)

def test_p100_pipeline_is_end_to_end():
    from core.pipeline.production import build_production_package
    p=build_production_package(
        takeoffs=[{"id":"T1","source_id":"S1","description":"بتن","quantity":3,"unit":"m3"}],
        boq=[{"price_code":"C001","description":"بتن","quantity":3,"unit":"m3","source":"S1","unit_price":100,"total":300}],
        estimate={"cost":{"base":300}},
        project_id="E2E")
    assert p["ready"] and p["validation"]["valid"] and p["totals"]["amount"]==300

def test_p101_iran_data_pack_has_provenance():
    from core.iran.data_pack import IranDataPack, DataPackEntry
    pack=IranDataPack([DataPackEntry("N9","مبحث 9","IR-NBR-09","1399")],"2026.1")
    m=pack.manifest()
    assert IranDataPack.verify(m) and m["pack_version"]=="2026.1"

def test_p102_report_bundle_hashes_files(tmp_path):
    from core.reports.bundle import build_bundle_manifest
    f=tmp_path/"report.xlsx"; f.write_bytes(b"demo")
    m=build_bundle_manifest([f],project_id="P",revision="R2")
    assert m["files"][0]["sha256"] and m["project_id"]=="P"

def test_p103_revision_impact_requires_review():
    from core.revisions.impact import build_impact_report
    r=build_impact_report([{"object_id":"B1","quantity":1}],[{"object_id":"B1","quantity":2}])
    assert r["summary"]["changed"]==1 and not r["finalizable"]

def test_p104_expanded_golden_dataset_exists():
    root=Path(__file__).parents[1]/"validation"/"golden_cases"
    cases=sorted(root.glob("GOLDEN-P104-*.json"))
    assert len(cases)>=5
    for p in cases:
        data=json.loads(p.read_text(encoding="utf-8"))
        assert data["case_id"].startswith("P104-") and data["dataset_version"]

def test_p105_hardening_gate():
    from core.performance.hardening import run_hardening_checks
    r=run_hardening_checks()
    assert r["ok"] and r["offline"] and r["fail_closed"]
