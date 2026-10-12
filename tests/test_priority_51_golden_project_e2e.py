"""Priority 51 — realistic project journey from creation to verified outputs."""
from __future__ import annotations

import json
from pathlib import Path

from core.platform.application import StructuralProApp
from core.projects.backup import BackupManager


def test_priority_51_golden_project_end_to_end(tmp_path: Path) -> None:
    """Exercise the main offline workflow without requiring the desktop UI."""
    app = StructuralProApp(tmp_path / "data")
    project_id = "golden-001"

    created = app.create_project("پروژه نمونه ساختمان", project_id)
    assert created["id"] == project_id

    slab = app.add_takeoff(
        project_id,
        "building",
        "slab",
        length=10,
        width=5,
        height=0.20,
        member_code="slab",
        price_code="SLAB-001",
        unit_price=1500000,
        source_id="drawing-A101-slab-01",
    )
    beam = app.add_takeoff(
        project_id,
        "building",
        "beam_concrete",
        length=6,
        width=0.30,
        depth=0.50,
        member_code="beam_concrete",
        price_code="BEAM-001",
        unit_price=2500000,
        source_id="drawing-S201-beam-01",
    )
    assert slab["quantities"][0]["amount"] > 0
    assert beam["quantities"][0]["amount"] > 0

    estimate = app.recalculate_estimate(project_id, factors={"waste": 0.05})
    assert estimate["validation"]["valid"]
    assert estimate["cost"]["grand_total"] > 0
    assert len(estimate["boq"]) == 2

    report_path = tmp_path / "golden-report.csv"
    app.report(project_id, "csv", report_path)
    assert report_path.exists() and report_path.stat().st_size > 0
    assert "SLAB-001" in report_path.read_text(encoding="utf-8")

    backup_path = tmp_path / "golden.spbackup"
    project = app.open_project(project_id)
    assert project is not None
    backup = BackupManager(tmp_path / "backups")
    package_path = backup.create_package(project, project_id)
    assert package_path.exists()
    restored = backup.restore_package(package_path)
    assert restored["id"] == project_id
    assert len(restored["takeoffs"]) == 2

    reopened = StructuralProApp(tmp_path / "data")
    reopened_project = reopened.open_project(project_id)
    assert reopened_project is not None
    assert len(reopened_project["takeoffs"]) == 2
    assert reopened_project["estimate"]["cost"]["grand_total"] == estimate["cost"]["grand_total"]

    validation = reopened.validate_project_data(project_id)
    assert validation["valid"]

    reliability = reopened.project_reliability_status(project_id)
    assert reliability["integrity"]["ok"]
    assert reliability["recoverable"]

    performance = reopened.project_performance_snapshot(project_id)
    assert performance["project_id"] == project_id

    page = reopened.project_collection_page(project_id, "takeoffs", page=1, page_size=1)
    assert page["total"] == 2
    assert len(page["items"]) == 1

    workflow = reopened.workflow_summary(project_id)
    assert isinstance(workflow, dict)

    export_path = tmp_path / "export.json"
    exported = reopened.export_project_backup(project_id, export_path)
    assert export_path.exists()
    assert exported["bytes"] > 0
    envelope = json.loads(export_path.read_text(encoding="utf-8"))
    assert envelope["project"]["id"] == project_id
