"""A deduction must preserve its physical amount, not merely its dimension.

All fixtures are synthetic. These tests protect typed manual BOQ inputs and
historical SQLite changes; they are not real-project/Windows acceptance.
"""
from copy import deepcopy
from decimal import Decimal

import pytest

from core.platform.application import StructuralProApp
from core.takeoff.manual_formula_register import clean
from core.takeoff.formulas import evaluate_rows
from test_manual_formula_persistence import data


def _deduction(variable_unit="m3", item_unit="m3", quantity="1"):
    return data(
        expression="length*width*height-void",
        variables={"length": "10", "width": "0.2", "height": "3", "void": quantity},
        variable_units={"length": "m", "width": "m", "height": "m", "void": variable_unit},
        deductions=[{
            "id": "geometry:void:1", "source_id": "geometry:void:1",
            "variable": "void", "quantity": quantity, "unit": item_unit,
            "basis": "حجم کسر از هندسه مستقل و اندازه گیری مستند مصنوعی",
        }],
    )


@pytest.mark.parametrize(("variable_unit", "item_unit"), [
    ("cm3", "m3"),
    ("mm3", "m3"),
    ("m3", "cm3"),
])
def test_same_dimension_different_scale_cannot_misstate_documented_deduction(
        variable_unit, item_unit):
    document = _deduction(variable_unit, item_unit)
    # These units are dimensionally equivalent, but "1" would mean a different
    # physical void. A successful AST dimensional check alone was insufficient.
    with pytest.raises(ValueError, match="واحد پارامتر کسر"):
        clean(document)


@pytest.mark.parametrize(("variable_unit", "item_unit"), [
    ("m3", "m3"), ("m3", "متر مکعب"), ("cm3", "cm3"),
])
def test_same_canonical_unit_remains_valid_and_exact(variable_unit, item_unit):
    document = clean(_deduction(variable_unit, item_unit))
    quantities = evaluate_rows({"A": {
        "expression": document["expression"], "variables": document["variables"],
        "variable_units": document["variable_units"],
        "unit_policy": document["unit_policy"], "references": {}, "unit": "m3",
    }})
    expected = Decimal("5") if variable_unit == "m3" else Decimal("5.999999")
    assert Decimal(str(quantities["A"])) == expected


def test_bulk_unit_tampering_is_atomic_and_cannot_change_stored_boq(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("آزمون فرضی کنترل کسر", "P")
    app.save_manual_formula(
        "P", "A", _deduction(), expected_revision=0, reason="ثبت کسر مستند",
    )
    original = deepcopy(app.open_project("P"))
    assert Decimal(str(app.load_manual_formulas("P")["A"]["quantity"])) == Decimal("5")
    with pytest.raises(ValueError, match="واحد پارامتر کسر"):
        app.bulk_edit_manual_formulas(
            "P", ["A"],
            changes={"variable_units": {"void": "cm3"}},
            expected_revisions={"A": 1},
            reason="آزمایش دستکاری واحد بدون تبدیل مقدار",
        )
    assert app.open_project("P") == original
    app.store.close()
    reopened = StructuralProApp(tmp_path)
    saved = reopened.load_manual_formulas("P")["A"]
    assert saved["revision"] == 1
    assert saved["data"]["variable_units"]["void"] == "m3"
    assert Decimal(str(saved["quantity"])) == Decimal("5")
    reopened.store.close()


def test_corrupted_typed_deduction_is_rejected_on_existing_row_reopen(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("آزمون ساختگی با داده مخدوش", "P")
    app.save_manual_formula(
        "P", "A", _deduction(), expected_revision=0, reason="ثبت صحیح",
    )
    project = app.open_project("P")
    project["manual_formula_register"]["A"]["data"]["variable_units"]["void"] = "cm3"
    app.store.save("P", project)
    with pytest.raises(ValueError, match="واحد پارامتر کسر"):
        app.load_manual_formulas("P")
    app.store.close()
