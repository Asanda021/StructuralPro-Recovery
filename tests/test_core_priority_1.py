import math
import pytest

from core.takeoff.units import convert, normalize_unit
from core.takeoff.formulas import evaluate
from core.takeoff.integrity import build_core_pipeline, normalize_takeoff_rows, convert_takeoff_unit
from core.takeoff.boq import build_boq

def test_units_are_canonical_and_convert_deterministically():
    assert normalize_unit("متر مربع") == "m2"
    assert convert(100, "cm", "m") == pytest.approx(1)
    assert convert(2, "ton", "kg") == pytest.approx(2000)
    assert convert(2, "m2", "cm2") == pytest.approx(20000)
    with pytest.raises(ValueError):
        convert(1, "m", "m2")

def test_formula_engine_rejects_non_finite_result():
    assert evaluate("a*b+c", {"a": 2, "b": 3, "c": 4}) == 10
    with pytest.raises((ValueError, ZeroDivisionError)):
        evaluate("1/0", {})
    with pytest.raises(ValueError):
        evaluate("__import__('os')", {})

def test_takeoff_normalization_blocks_duplicates_and_bad_values():
    rows = normalize_takeoff_rows([
        {"id": "T1", "source_id": "DRAW-1", "quantity": 100, "unit": "cm"},
    ], project_id="P1")
    assert rows[0]["unit"] == "cm"
    assert convert_takeoff_unit(rows[0], "m")["quantity"] == pytest.approx(1)
    with pytest.raises(ValueError):
        normalize_takeoff_rows([
            {"id": "T1", "source_id": "DRAW-1", "quantity": 1, "unit": "m"},
            {"id": "T2", "source_id": "DRAW-1", "quantity": 2, "unit": "m"},
        ])
    with pytest.raises(ValueError):
        normalize_takeoff_rows([{"quantity": -1, "unit": "m"}])

def test_boq_rejects_invalid_quantity_and_factor():
    with pytest.raises(ValueError):
        build_boq([{"description": "x", "quantity": -1, "unit": "m"}])
    with pytest.raises(ValueError):
        build_boq([{"description": "x", "quantity": 1, "unit": "m", "factor": -2}])

def test_canonical_project_takeoff_boq_estimate_chain():
    project = {"id": "P1", "name": "پروژه تست"}
    rows = [
        {"id": "T1", "source_id": "DRAW-1", "description": "دیوار", "quantity": 10,
         "unit": "m", "price_code": "W001", "unit_price": 1200},
        {"id": "T2", "source_id": "DRAW-2", "description": "دیوار", "quantity": 5,
         "unit": "m", "price_code": "W001", "unit_price": 1200},
    ]
    result = build_core_pipeline(project, rows, factors={"سربار": 0.1})
    assert result["integrity"]["healthy"] is True
    assert result["boq_summary"]["line_count"] == 1
    assert result["boq"][0]["quantity"] == 15
    assert result["estimate"]["cost"]["base"] == 18000
    assert result["estimate"]["cost"]["grand_total"] == pytest.approx(19800)

def test_project_pipeline_does_not_silently_double_count_same_source():
    project = {"id": "P2", "name": "بدون دوباره‌شماری"}
    rows = [
        {"id": "T1", "source_id": "DWG-A-17", "description": "ستون", "quantity": 4,
         "unit": "عدد", "price_code": "C001", "unit_price": 100},
        {"id": "T2", "source_id": "DWG-A-17", "description": "ستون", "quantity": 4,
         "unit": "عدد", "price_code": "C001", "unit_price": 100},
    ]
    with pytest.raises(ValueError, match="دوباره"):
        build_core_pipeline(project, rows)

def test_application_rejects_duplicate_takeoff_source(tmp_path):
    from core.platform.application import StructuralProApp
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه منبع", "P3")
    app.add_takeoff("P3", "building", "wall", source_id="DRAW-9",
                    length=2, width=0.2, height=3, price_code="W001", unit_price=100)
    with pytest.raises(ValueError, match="دوباره"):
        app.add_takeoff("P3", "building", "wall", source_id="DRAW-9",
                        length=2, width=0.2, height=3, price_code="W001", unit_price=100)

from core.pricing.catalog import PriceCatalog, PriceItem
from core.takeoff.estimate import build_estimate, compare_estimates

def test_stage3_price_catalog_custom_price_and_history():
    catalog = PriceCatalog([PriceItem(1405,"ابنیه","فصل 1","W001","دیوار","m",1200)])
    catalog.add(PriceItem(1405,"ابنیه","فصل 1","W001","دیوار","m",1300))
    assert catalog.price_history("W001",1405)[0]["old_price"] == 1200
    catalog.set_custom_price("W001",1405,1450,reason="قیمت پیمانکار")
    assert catalog.get("W001",1405).unit_price == 1450
    catalog.clear_custom_price("W001",1405)
    assert catalog.get("W001",1405).unit_price == 1300
    with pytest.raises(ValueError):
        catalog.add(PriceItem(1405,"","","BAD","x","m",float("nan")))

def test_stage3_estimate_comparison_reports_line_changes():
    old = build_estimate([{"source":"A","description":"دیوار","quantity":10,"unit":"m","price_code":"W001","unit_price":100}], aggregate=False)
    new = build_estimate([{"source":"B","description":"دیوار","quantity":12,"unit":"m","price_code":"W001","unit_price":110}], aggregate=False)
    result = compare_estimates(old,new)
    assert result["delta"] == 320
    assert result["line_changes"][0]["quantity_delta"] == 2
    assert result["line_changes"][0]["unit_price_delta"] == 10
