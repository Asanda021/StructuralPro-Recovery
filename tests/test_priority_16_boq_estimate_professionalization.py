from core.takeoff.boq import build_boq, validate_boq_structure, boq_summary
from core.takeoff.estimate import build_estimate

def test_professional_boq_preserves_coding_and_provenance():
    rows = build_boq([{
        "source": "pdf:p1:T1", "source_id": "pdf:p1:T1", "source_type": "takeoff",
        "item_code": "CONC-001", "price_code": "M-001", "chapter": "بتن",
        "category": "سازه", "group": "بتن", "description": "بتن فونداسیون",
        "quantity": 10, "unit": "m3", "unit_price": 2500000,
    }])
    row = rows[0]
    assert row["item_code"] == "CONC-001"
    assert row["source_id"] == "pdf:p1:T1"
    assert row["source_type"] == "takeoff"
    assert row["chapter"] == "بتن"
    assert row["total"] == 25000000

def test_boq_structure_reports_missing_code_as_warning_and_missing_description_as_error():
    result = validate_boq_structure([
        {"description": "A", "quantity": 1, "unit": "m3", "status": "active"},
        {"description": "", "quantity": 1, "unit": "m3", "status": "active"},
    ])
    assert result["valid"] is False
    assert any(x["code"] == "missing_item_code" for x in result["warnings"])
    assert any(x["code"] == "missing_description" for x in result["errors"])

def test_boq_summary_groups_amounts():
    rows = build_boq([
        {"item_code": "A", "description": "بتن", "quantity": 2, "unit": "m3", "unit_price": 100, "group": "بتن"},
        {"item_code": "B", "description": "میلگرد", "quantity": 3, "unit": "kg", "unit_price": 20, "group": "آرماتور"},
    ], aggregate=False)
    summary = boq_summary(rows)
    assert summary["grand_total"] == 260
    assert summary["amount_by_group"] == {"بتن": 200, "آرماتور": 60}

def test_cancelled_boq_line_is_not_costed():
    estimate = build_estimate([
        {"item_code": "A", "description": "فعال", "quantity": 2, "unit": "m3", "unit_price": 100},
        {"item_code": "B", "description": "لغوشده", "quantity": 5, "unit": "m3", "unit_price": 100, "status": "cancelled"},
    ], aggregate=False)
    assert estimate["cost"]["base"] == 200

def test_estimate_rejects_invalid_factor_and_exposes_validation():
    try:
        build_estimate([{"description": "A", "quantity": 1, "unit": "m3"}], factors={"overhead": -0.1})
    except ValueError:
        pass
    else:
        raise AssertionError("negative estimate factor was accepted")
    estimate = build_estimate([{"item_code": "A", "description": "A", "quantity": 1, "unit": "m3"}])
    assert estimate["validation"]["valid"] is True
    assert estimate["factors"] == {}


def test_price_catalog_accepts_common_unit_aliases():
    from core.pricing.catalog import PriceCatalog, PriceItem
    c=PriceCatalog([PriceItem(1405,"g","c","A","Concrete","m3",100)])
    assert c.resolve("A",1405,"مترمکعب")["status"]=="ok"
