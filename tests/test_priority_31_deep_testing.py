"""Priority 31 — deep cross-system and boundary testing.

These tests exercise real application services together rather than only isolated
helpers. They intentionally stay offline and use temporary project databases/files.
"""
from __future__ import annotations

import json

import pytest

from core.ai.engineering_assistant import EngineeringAssistant
from core.drawings.model_registry import ModelObject, ModelSource
from core.platform.application import StructuralProApp
from core.performance.project_performance import paginate
from core.pricing.catalog import PriceCatalog, PriceItem
from core.recovery.recovery import RecoveryError, import_project
from core.reports.project_report import build_report
from core.takeoff.engine import TakeoffEngine


def test_end_to_end_project_takeoff_boq_estimate(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    created = app.create_project("Deep Test", "P-31")
    assert created["id"] == "P-31"

    row = app.add_takeoff(
        "P-31", "building", "slab_volume",
        length=5, width=4, thickness=0.2, price_code="A-1", source_id="drawing:1"
    )
    assert row["quantities"][0]["amount"] == pytest.approx(4.0)

    estimate = app.recalculate_estimate("P-31")
    assert estimate["validation"]["valid"]
    assert estimate["boq"]
    assert estimate["cost"]["base"] >= 0

    project = app.open_project("P-31")
    assert project is not None
    assert len(project["takeoffs"]) == 1
    assert len(project["boq"]) == 1


def test_duplicate_takeoff_source_is_blocked_without_mutating_project(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("Duplicate Test", "P-31")
    app.add_takeoff("P-31", "building", "slab", length=2, width=2, height=0.2, source_id="S1")
    with pytest.raises(ValueError, match="تکراری"):
        app.add_takeoff("P-31", "building", "slab", length=3, width=3, height=0.2, source_id="S1")
    project = app.open_project("P-31")
    assert project is not None and len(project["takeoffs"]) == 1


def test_takeoff_batch_and_summary_are_consistent():
    engine = TakeoffEngine()
    rows = engine.batch([
        {"domain": "building", "item": "slab_volume", "length": 2, "width": 3, "thickness": 0.2},
        {"domain": "building", "item": "slab_volume", "length": 1, "width": 4, "thickness": 0.2},
    ])
    summary = engine.summarize(rows)
    assert summary["row_count"] == 2
    assert summary["quantity_by_unit"]["m3"] == pytest.approx(2.0)


def test_invalid_estimate_factors_fail_closed(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("Factor Test", "P-31")
    app.add_takeoff("P-31", "building", "slab", length=2, width=2, height=0.2)
    with pytest.raises(ValueError):
        app.recalculate_estimate("P-31", factors={"overhead": -0.1})
    with pytest.raises(ValueError):
        app.recalculate_estimate("P-31", factors={"overhead": float("inf")})


def test_price_catalog_round_trip_and_custom_price():
    catalog = PriceCatalog([
        PriceItem(1405, "building", "01", "100", "Concrete", "m3", 1000),
    ])
    exported = catalog.export_csv(1405)
    restored = PriceCatalog()
    assert restored.import_csv(exported) == 1
    assert restored.resolve("100", 1405)["status"] == "ok"
    custom = restored.set_custom_price("100", 1405, 1250, reason="approved")
    assert custom.unit_price == 1250
    assert restored.get("100", 1405).unit_price == 1250
    restored.clear_custom_price("100", 1405)
    assert restored.get("100", 1405).unit_price == 1000


def test_backup_and_project_export_import_round_trip(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("Recovery Test", "P-31")
    app.add_takeoff("P-31", "building", "slab", length=2, width=3, height=0.2)

    db_backup = tmp_path / "backup.db"
    backup = app.backup_project_database(db_backup)
    assert db_backup.exists() and backup["size"] > 0
    assert app.project_reliability_status("P-31")["integrity"]["ok"]

    project_backup = tmp_path / "project.json"
    exported = app.export_project_backup("P-31", project_backup)
    imported = app.import_project_backup(project_backup)
    assert exported["bytes"] > 0
    assert imported["id"] == "P-31"
    assert imported["name"] == "Recovery Test"


def test_corrupt_project_backup_is_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"format": "wrong", "schema_version": 1}), encoding="utf-8")
    with pytest.raises(RecoveryError):
        import_project(path)


def test_performance_pagination_boundaries():
    rows = list(range(205))
    first = paginate(rows, page=1, page_size=100)
    last = paginate(rows, page=3, page_size=100)
    assert first["total"] == 205 and first["has_next"]
    assert len(first["items"]) == 100
    assert len(last["items"]) == 5 and not last["has_next"]
    with pytest.raises(ValueError):
        paginate(rows, page=0, page_size=100)


def test_ai_review_is_read_only_and_requires_confirmation_for_mutation_words(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("AI Test", "P-31")
    before = app.open_project("P-31")
    response = app.ai_assistant_respond("P-31", "متره پروژه را بررسی کن و ثبت کن")
    after = app.open_project("P-31")
    assert response["intent"] == "takeoff_review"
    assert response["requires_confirmation"]
    assert response["deterministic"] and response["offline"]
    assert before == after


def test_model_registry_maps_objects_with_provenance_and_confirmation(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("Model Test", "P-31")
    app.register_model_source(
        "P-31", ModelSource(id="SRC1", path="model.ifc", format="ifc", revision="2")
    )
    app.add_model_object(
        "P-31",
        ModelObject(
            source_id="SRC1", object_id="W1", object_type="Wall",
            name="Wall 1", level="L1", quantities={"Volume": 12.5}
        ),
    )
    preview = app.project_model_takeoff_preview(
        "P-31", mapping={"Wall": "W-01"}, source_id="SRC1"
    )
    assert preview["unmapped"] == []
    assert preview["rows"][0]["quantity"] == pytest.approx(12.5)
    assert preview["rows"][0]["source_id"] == "SRC1"
    assert preview["rows"][0]["needs_confirmation"] is False


def test_model_registry_requires_mapping_when_requested(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("Model Mapping Test", "P-31")
    app.register_model_source(
        "P-31", ModelSource(id="SRC1", path="model.ifc", format="ifc")
    )
    app.add_model_object(
        "P-31",
        ModelObject(source_id="SRC1", object_id="C1", object_type="Column",
                    quantities={"Count": 4}),
    )
    preview = app.project_model_takeoff_preview(
        "P-31", mapping={}, source_id="SRC1", require_mapping=True
    )
    assert preview["rows"] == []
    assert preview["unmapped"] == ["C1"]


def test_project_report_validation_and_column_contract():
    report = build_report(
        "گزارش آزمون",
        [{"description": "بتن", "quantity": 10, "unit": "m3", "price_code": "100"}],
        summary={"total": 10},
    )
    validation = report.validate()
    assert validation["valid"] and validation["line_count"] == 1
    assert ("description", "شرح") in report.columns()
    assert ("quantity", "مقدار") in report.columns()


def test_project_report_rejects_missing_description():
    report = build_report("Test", [{"quantity": 1, "unit": "m3"}])
    assert not report.validate()["valid"]


def test_missing_project_contracts_fail_cleanly(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    assert app.open_project("missing") is None
    with pytest.raises(KeyError):
        app.project_performance_snapshot("missing")
    with pytest.raises(KeyError):
        app.ai_assistant_context("missing")


def test_database_reopen_preserves_project_data(tmp_path):
    data_dir = tmp_path / "data"
    app = StructuralProApp(data_dir)
    app.create_project("Persistence Test", "P-31")
    app.add_takeoff("P-31", "building", "slab", length=2, width=2, height=0.2)
    app.store.close()

    reopened = StructuralProApp(data_dir)
    project = reopened.open_project("P-31")
    assert project is not None
    assert project["name"] == "Persistence Test"
    assert len(project["takeoffs"]) == 1
    assert reopened.project_reliability_status("P-31")["integrity"]["ok"]
