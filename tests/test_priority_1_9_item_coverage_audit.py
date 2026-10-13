"""Regression guards for the full item coverage baseline of priorities 1–9."""
import copy
from pathlib import Path

import pytest

from core.product.aec_item_inventory_audit import (
    assert_priority_inventory, verify_priority_inventory,
)
from core.takeoff.reviewed_aec import SPECS, empty_system, preview_system
from core.takeoff.engine import TakeoffEngine
from core.engineering.domains.steel import steel_quantities


def test_nine_priorities_have_independent_item_audit_manifest():
    result = assert_priority_inventory()
    assert result["family_count"] >= 83
    assert result["subitem_mentions"] >= 856
    assert result["reviewed_aec_contracts"] == len(SPECS)
    assert set(result["priority_counts"]) == set(map(str, range(1, 10)))
    assert not result["release_ready"] and result["production_items_verified"] == 0


@pytest.mark.parametrize("kind", sorted(SPECS))
def test_every_catalogued_aec_item_is_unreviewed_by_default(kind):
    data = empty_system(kind, "L1", "X1")
    result = preview_system(data, TakeoffEngine())
    assert not result["ready"]
    assert result["blockers"] and result["rows"] == []


def test_unlisted_family_is_detected(tmp_path):
    import json
    original = Path(__file__).resolve().parents[1] / "docs" / (
        "aec_priority_1_9_master_inventory_20261013.json")
    data = json.loads(original.read_text(encoding="utf-8"))
    data["items"] = [row for row in data["items"] if row["code"] != "steel_deck"]
    data["priority_family_count"] -= 1
    data["component_mentions_count"] = sum(len(row["components"]) for row in data["items"])
    changed = tmp_path / "incomplete.json"
    changed.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    result = verify_priority_inventory(changed)
    assert not result["valid"]
    assert any("قرارداد AEC" in issue for issue in result["issues"])


def test_false_production_acceptance_is_rejected(tmp_path):
    import json
    original = Path(__file__).resolve().parents[1] / "docs" / (
        "aec_priority_1_9_master_inventory_20261013.json")
    data = json.loads(original.read_text(encoding="utf-8"))
    data["items"][0]["fully_accepted"] = True
    changed = tmp_path / "unproven.json"
    changed.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert not verify_priority_inventory(changed)["valid"]


def test_weld_weight_no_longer_fabricates_one_kg_per_m():
    with pytest.raises(KeyError):
        steel_quantities("weld", length=3, count=2)
    q = steel_quantities("weld", length=3, count=2, weld_unit_weight=.08)
    assert q.quantity == pytest.approx(.48)


def test_joist_arrangement_must_be_entered_not_inferred_from_spacing():
    with pytest.raises(KeyError):
        TakeoffEngine().calculate(
            "building", "joist_foam_roof", length=5, width=6, count=1,
            topping_thickness=.05, joist_spacing=.5,
            joist_width=.10, joist_depth=.20)
    out = TakeoffEngine().calculate(
        "building", "joist_foam_roof", length=5, width=6, count=1,
        topping_thickness=.05, joist_spacing=.5,
        joist_width=.10, joist_depth=.20, joist_count=13)
    assert out.quantity == pytest.approx(2.8)


def test_stair_ui_asks_for_sloped_waist_geometry_not_box_dimensions():
    ui_path = Path(__file__).resolve().parents[1] / "app" / "aec_workspace.py"
    source = ui_path.read_text(encoding="utf-8")
    assert '("stair_concrete","پله بتنی",("sloped_length","width","waist_thickness","count"))' in source


@pytest.mark.parametrize("value", ["", "  ", "nan", "inf", "-inf", "-1"])
def test_pricebook_import_never_silently_defaults_missing_or_nonfinite_price(value):
    from core.pricing.import_service import PricebookImportService
    with pytest.raises(ValueError):
        PricebookImportService._number(value)


def test_nonfinite_prices_cannot_pass_generic_pricing():
    from core.pricing.production import validate_dataset_rows, price_analysis
    valid = {"year": 1405, "group": "ابنیه", "chapter": "1",
             "code": "010101", "description": "بتن",
             "unit": "m3", "unit_price": float("nan")}
    assert not validate_dataset_rows([valid])["valid"]
    with pytest.raises(ValueError):
        price_analysis(1.0, float("nan"))
    with pytest.raises(ValueError):
        price_analysis(2, 100, factors=(float("inf"),))


def test_legacy_building_scope_rejects_nan_quantities():
    from core.product.full_building_takeoff_v2 import TakeoffScope, validate_scope
    item = TakeoffScope("concrete", "beam", "بتن", "m3", float("nan"), "manual:C1")
    with pytest.raises(ValueError):
        validate_scope([item])


def test_manual_aec_assembly_is_not_committed_as_multiple_partial_transactions():
    ui = (Path(__file__).resolve().parents[1] / "app" / "aec_workspace.py"
          ).read_text(encoding="utf-8")
    assert "service.add_assembly_takeoff(" in ui
    assert "AssemblyTemplateLibrary" in ui
    assert "floor_input.text().strip()" in ui
    assert "joist_count" in ui
    assert "این سقف به دیتایل‌های واقعی" in ui
    assert 'w.setValue(0)' in ui
