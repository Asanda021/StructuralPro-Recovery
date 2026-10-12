import json
from pathlib import Path
from core.platform.parity import capability_matrix

ROOT = Path(__file__).parents[1]
CATALOG = ROOT / "website" / "data" / "products.json"

EXPECTED = {
    "StructuralPro Takeoff","StructuralPro CAD Takeoff","StructuralPro BIM Takeoff","StructuralPro BOQ","StructuralPro Estimating",
    "StructuralPro Technical Office","StructuralPro Site Supervisor","StructuralPro Project Controls","StructuralPro Project Manager",
    "StructuralPro Cost Control","StructuralPro Contract & Claims","StructuralPro Procurement","StructuralPro BIM & Coordination",
    "StructuralPro Reports & Intelligence","StructuralPro AI & AEC Assistant","StructuralPro Price & Cost Intelligence",
    "StructuralPro Structural Analysis & Design","StructuralPro Geotechnical","StructuralPro Architecture","StructuralPro MEP",
    "StructuralPro Civil & Site","StructuralPro Concrete Engineering","StructuralPro Steel Engineering","StructuralPro Masonry Engineering",
    "StructuralPro Timber Engineering","StructuralPro Composite Structures","StructuralPro Precast","StructuralPro Special Structures",
    "StructuralPro Tender & Bid Management","StructuralPro AEC Enterprise",
}

def load():
    return json.loads(CATALOG.read_text(encoding="utf-8"))

def products(data):
    return [p for c in data["categories"] for p in c["products"]]

def test_catalog_is_exact_30_product_architecture():
    data = load()
    rows = products(data)
    assert len(rows) == 30
    assert len([p for p in rows if not p.get("platform")]) == 29
    assert len([p for p in rows if p.get("platform")]) == 1
    assert {p["name"] for p in rows} == EXPECTED
    assert data["specialized_product_count"] == 29
    assert data["enterprise_platform_count"] == 1

def test_catalog_status_and_capability_ids_match_software():
    rows = products(load())
    valid_statuses = {"Available", "Integration", "Planned"}
    valid_capabilities = {c["id"] for c in capability_matrix()}
    for product in rows:
        assert product["status"] in valid_statuses
        assert product["id"].strip()
        for capability_id in product.get("capability_ids", []):
            assert capability_id in valid_capabilities

def test_no_duplicate_product_ids_and_enterprise_isolated():
    rows = products(load())
    ids = [p["id"] for p in rows]
    assert len(ids) == len(set(ids))
    assert [p["id"] for p in rows if p.get("platform")] == ["aec-enterprise"]
