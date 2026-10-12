from core.estimate.pricebook_import_v2 import import_csv, dataset_fingerprint, year_coverage
from core.estimate.pricebook_mapping_v2 import map_item
from core.validation.iranian_project_benchmark_v2 import BenchmarkRow, compare
from core.cloud.collaboration_v3 import CollaborationEvent, apply_event
from core.product.ux_readiness_v2 import score_product_surface


def test_pricebook_import_and_year_coverage():
    rows = import_csv(
        "year,item_code,description,unit,rate\n1404,1001,Concrete,m3,12500000\n1405,1001,Concrete,m3,14000000\n",
        "official-file:fixture"
    )
    assert len(rows) == 2
    assert year_coverage(rows, {1404, 1405})["complete"]
    assert dataset_fingerprint(rows)


def test_mapping_is_exact_when_evidence_matches():
    result = map_item("t1", "Concrete", "m3", [{"item_code": "1001", "description": "Concrete", "unit": "m3"}])
    assert result.item_code == "1001"
    assert result.confidence == 1.0
    assert not result.review_required


def test_real_project_benchmark_green2():
    result = compare([BenchmarkRow("a", 100.0, 99.0), BenchmarkRow("b", 200.0, 202.0)])
    assert result["green2"]


def test_cloud_conflict_is_explicit():
    event = CollaborationEvent("p", 2, "u", "old", "new", "update")
    assert apply_event(1, "current", event)["conflict"]


def test_ux_green2_surface():
    surface = {"actions": ["edit", "back", "menu", "restart", "review", "calculate"],
               "rtl": True, "stage_input": True, "review_gate": True}
    assert score_product_surface([surface])["green2"]
