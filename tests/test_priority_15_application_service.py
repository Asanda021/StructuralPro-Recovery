from core.platform.application import StructuralProApp

def test_application_exposes_engineering_library(tmp_path):
    app = StructuralProApp(tmp_path)
    status = app.engineering_library_status()
    assert status["ok"] is True
    assert status["counts"]["concretes"] == 5
    assert app.engineering.concrete("C30").characteristic_strength_mpa == 30

def test_application_engineering_search_does_not_require_project(tmp_path):
    app = StructuralProApp(tmp_path)
    rows = app.search_engineering_library("A3", category="rebar")
    assert [row["code"] for row in rows] == ["A3"]
