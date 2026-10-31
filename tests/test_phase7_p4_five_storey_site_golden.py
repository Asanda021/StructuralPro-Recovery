"""P7 P4: genuine five-floor synthetic site fixture, no customer data."""
from copy import deepcopy
from hashlib import sha256
import json

from core.platform.application import StructuralProApp
from core.reports.technical_office_dossier import export_verified_site_controls_dossier


def test_five_floor_office_records_and_site_reports_are_source_backed(tmp_path):
    from scripts.phase4_site_operations_probe import run

    root = tmp_path / "synthetic_five_floor_site"
    result = run(root)
    assert result["synthetic"] is True
    assert result["immutable_originals"] and result["reopen_equal"]
    app = StructuralProApp(root / "prior" / "engineering" / "db")
    state = app.open_project("P")
    original = deepcopy(state)
    digest = app.store.current_digest("P")
    types = ("resources", "materials", "daily", "meetings", "correspondence")
    output = tmp_path / "site_office_five_floor_dossier"
    try:
        issued = export_verified_site_controls_dossier(
            app, project_id="P",
            expected_project_version=state["_meta"]["version"],
            as_of="2026-05-02", selected_kinds=types,
            destination=output,
        )
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        assert issued["manifest"] == manifest
        assert manifest["report_count"] == len(types) == len(manifest["reports"])
        assert manifest["source_project_digest"] == digest
        assert manifest["financial_mutation"] is False
        assert manifest["as_of"] == "2026-05-02"
        assert set(r["kind"] for r in manifest["reports"]) == set(types)
        assert len(manifest["files"]) >= len(types) * 4
        assert all(len(report["files"]) == 4 for report in manifest["reports"])
        for entry in manifest["files"]:
            path = output / entry["name"]
            assert path.stat().st_size == entry["size"] > 0
            assert sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        assert state == original == app.open_project("P")
        assert app.store.current_digest("P") == digest
    finally:
        app.store.close()
