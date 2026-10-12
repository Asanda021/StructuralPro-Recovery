"""Priority 35 — real-world golden project scenarios."""
from __future__ import annotations

from core.platform.application import StructuralProApp
from core.benchmark.golden import GoldenCase, acceptance_summary, run_case


def _app(tmp_path):
    app = StructuralProApp(tmp_path / "data")
    app.create_project("Golden Residential", "G35")
    return app


def test_residential_concrete_quantity_workflow(tmp_path):
    app = _app(tmp_path)
    rows = [
        ("F1", "column", dict(width=0.4, depth=0.4, height=3.2, count=8)),
        ("B1", "beam", dict(width=0.3, depth=0.5, length=6.0, count=10)),
        ("S1", "slab_volume", dict(length=12.0, width=10.0, thickness=0.2)),
    ]
    for source_id, item, params in rows:
        app.add_takeoff("G35", "building", item, source_id=source_id, **params)
    estimate = app.recalculate_estimate("G35")
    project = app.open_project("G35")
    assert len(project["takeoffs"]) == 3
    assert len(estimate["boq"]) == 3
    assert estimate["validation"]["valid"] is True


def test_recovery_and_recalculation_scenario(tmp_path):
    app = _app(tmp_path)
    app.add_takeoff("G35", "building", "slab_volume",
                    length=20, width=15, thickness=0.2, source_id="DRAW-SLAB")
    first = app.recalculate_estimate("G35")
    backup = tmp_path / "golden.json"
    app.export_project_backup("G35", backup)
    imported = app.import_project_backup(backup)
    assert imported["id"] == "G35"
    second = app.recalculate_estimate("G35")
    assert first["boq"] == second["boq"]


def test_golden_acceptance_covers_multiple_project_surfaces(tmp_path):
    app = _app(tmp_path)

    def factory(case):
        if case.case_id == "quantity":
            app.add_takeoff("G35", "building", "slab_volume",
                            length=10, width=8, thickness=0.2)
            return app.open_project("G35")
        if case.case_id == "estimate":
            app.recalculate_estimate("G35")
            return app.open_project("G35")
        if case.case_id == "performance":
            return app.project_performance_snapshot("G35")
        raise KeyError(case.case_id)

    cases = [
        GoldenCase("quantity", "quantity takeoff scenario", ("takeoffs",)),
        GoldenCase("estimate", "estimate persistence scenario", ("estimate",)),
        GoldenCase("performance", "large-project metrics scenario", ("project_id", "collection_counts")),
    ]
    results = [run_case(case, factory) for case in cases]
    summary = acceptance_summary(results)
    assert summary["ready"] is True
    assert summary["passed"] == 3


def test_large_collection_pagination_scenario(tmp_path):
    app = _app(tmp_path)
    for i in range(120):
        app.add_takeoff("G35", "building", "slab_volume",
                        length=1 + i, width=2, thickness=0.2, source_id=f"ROW-{i}")
    page = app.project_collection_page("G35", "takeoffs", page=3, page_size=50)
    assert page["total"] == 120
    assert len(page["items"]) == 20
    assert page["has_previous"] is True
    assert page["has_next"] is False
