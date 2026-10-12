"""Priority 48 — reporting and export integrity audit."""
import math
import pytest
from core.reports import build_report

def test_report_rejects_non_finite_and_negative_numeric_values(tmp_path):
    for row in (
        {"description":"بتن","quantity":math.nan,"unit":"m3"},
        {"description":"بتن","quantity":-1,"unit":"m3"},
        {"description":"بتن","quantity":1,"unit":"m3","total":math.inf},
    ):
        report=build_report("پروژه",[row])
        assert not report.validate()["valid"]
        with pytest.raises(ValueError,match="invalid report"):
            report.export(tmp_path/"invalid.xlsx","xlsx")

def test_report_rejects_duplicate_item_numbers():
    rows=[{"item_no":1,"description":"الف","quantity":1,"unit":"m3"},
          {"item_no":1,"description":"ب","quantity":2,"unit":"m3"}]
    report=build_report("پروژه",rows)
    result=report.validate()
    assert not result["valid"]
    assert any("duplicate_item_no" in x for x in result["errors"])
