from core.pricing.catalog import PriceCatalog, PriceItem
from core.takeoff.boq import build_boq, boq_summary
from core.takeoff.costing import cost_breakdown


def test_price_catalog_year_group_chapter_search_and_snapshot():
    c = PriceCatalog([PriceItem(1405, "ابنیه", "بتن", "A-1", "بتن آماده", "m3", 1200000)])
    assert c.years() == [1405]
    assert c.groups(1405) == ["ابنیه"]
    assert c.chapters(1405, "ابنیه") == ["بتن"]
    assert c.search("بتن", 1405)[0].code == "A-1"
    assert c.resolve("A-1", 1405, "m3")["status"] == "ok"
    assert c.snapshot(["A-1"], 1405)[0]["unit_price"] == 1200000


def test_price_catalog_resolution_errors():
    c = PriceCatalog([
        PriceItem(1405, "ابنیه", "بتن", "A-1", "بتن", "m3", 100),
        PriceItem(1405, "ابنیه", "بتن", "A-2", "بتن بدون قیمت", "m3", 0),
    ])
    assert c.resolve("X", 1405)["status"] == "not_found"
    assert c.resolve("A-1", 1405, "kg")["status"] == "unit_mismatch"
    assert c.resolve("A-2", 1405, "m3")["status"] == "zero_price"


def test_price_catalog_csv_round_trip():
    c = PriceCatalog([PriceItem(1405, "ابنیه", "بتن", "A-1", "بتن آماده", "m3", 1200000)])
    csv_text = c.export_csv(1405)
    other = PriceCatalog()
    assert other.import_csv(csv_text) == 1
    assert other.get("A-1", 1405).unit_price == 1200000


def test_boq_aggregate_and_summary():
    rows = [
        {"source": "drawing", "description": "Concrete", "quantity": 2, "unit": "m3", "price_code": "A", "unit_price": 100},
        {"source": "drawing", "description": "Concrete", "quantity": 3, "unit": "m3", "price_code": "A", "unit_price": 100},
    ]
    boq = build_boq(rows)
    assert len(boq) == 1
    assert boq[0]["quantity"] == 5
    assert boq[0]["total"] == 500
    assert boq_summary(boq)["grand_total"] == 500


def test_boq_preserves_separate_units_and_warns_zero_price():
    rows = [
        {"description": "Concrete", "quantity": 2, "unit": "m3", "price_code": "A", "unit_price": 0},
        {"description": "Concrete", "quantity": 200, "unit": "kg", "price_code": "A", "unit_price": 10},
    ]
    boq = build_boq(rows)
    assert len(boq) == 2
    assert "zero_price" in boq[0]["warning"]
    assert boq_summary(boq)["line_count"] == 2


def test_boq_factor_is_applied_to_line_total():
    rows = build_boq([
        {"description": "Concrete", "quantity": 2, "unit": "m3", "price_code": "A", "unit_price": 100, "factor": 1.1}
    ])
    assert rows[0]["total"] == 220


def test_costing_factors():
    out = cost_breakdown(
        [{"group": "ابنیه", "price_code": "A", "quantity": 2, "unit_price": 100}],
        {"بالاسری": 0.1},
    )
    assert out["base"] == 200
    assert out["grand_total"] == 220
    assert out["by_group"]["ابنیه"] == 200
    assert out["by_code"]["A"] == 200


def test_costing_multiple_factors_are_sequential():
    out = cost_breakdown(
        [{"quantity": 100, "unit_price": 1}],
        {"بالاسری": 0.1, "منطقه‌ای": 0.2},
    )
    assert out["base"] == 100
    assert out["factors"]["بالاسری"] == 10
    assert out["factors"]["منطقه‌ای"] == 22
    assert out["grand_total"] == 132
