"""Priority 9: regression, determinism, edge-case and integrity QA gates."""
import importlib
import json
from pathlib import Path

from core.history.project_commands import ProjectHistory
from core.projects.audit import AuditTrail
from core.projects.backup import BackupManager
from core.projects.import_export import export_project, fingerprint, import_project
from core.projects.integrity import validate_project
from core.projects.workflow import project_health
from core.revisions.manager import RevisionManager


def project():
    return {
        "id": "QA-1",
        "name": "QA Project",
        "client": "Client",
        "contractor": "Contractor",
        "contract_number": "CN-1",
        "drawings": [{"id": "D1", "path": "plan.pdf"}],
        "takeoffs": [{"id": "T1", "quantity": 10}],
        "boq": [{"id": "B1", "quantity": 10, "unit_price": 100}],
        "estimates": [{"id": "E1", "total": 1000}],
    }


def test_import_all_core_modules():
    modules = []
    for path in Path("core").rglob("*.py"):
        if path.name == "__init__.py":
            continue
        module = ".".join(path.with_suffix("").parts)
        modules.append(module)
    for module in modules:
        importlib.import_module(module)


def test_project_integrity_edge_cases():
    p = project()
    assert validate_project(p)["valid"]
    bad = json.loads(json.dumps(p))
    bad["takeoffs"][0]["quantity"] = float("nan")
    bad["boq"][0]["unit_price"] = float("inf")
    bad["estimates"][0]["project_id"] = "UNKNOWN"
    result = validate_project(bad)
    codes = {issue["code"] for issue in result["issues"]}
    assert {"invalid_number", "broken_reference"} <= codes
    assert not result["valid"]


def test_export_is_canonical_and_round_trip_is_lossless():
    p = project()
    first = export_project(p)
    second = export_project(json.loads(json.dumps(p)))
    assert first == second
    assert import_project(first) == p
    assert fingerprint(p) == fingerprint(import_project(first))


def test_history_failed_mutation_is_atomic():
    p = {"id": "QA-1", "name": "before", "meta": {"status": "ok"}}
    history = ProjectHistory(p)
    try:
        history.set_value(["meta", "missing", "value"], 1)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid command must fail")
    assert p == {"id": "QA-1", "name": "before", "meta": {"status": "ok"}}
    history.set_value(["meta", "status"], "changed")
    assert history.undo() and p["meta"]["status"] == "ok"
    assert history.redo() and p["meta"]["status"] == "changed"


def test_revision_snapshots_are_isolated_and_invalid_restore_is_rejected():
    rows = [{"code": "A", "quantity": 1, "total": 10}]
    manager = RevisionManager()
    manager.add(rows, "v1")
    rows[0]["quantity"] = 99
    assert manager.latest().rows[0]["quantity"] == 1
    try:
        manager.restore(999)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown revision must fail")


def test_backup_package_rejects_tampering(tmp_path):
    manager = BackupManager(tmp_path)
    path = manager.create_package(project(), "QA-1")
    assert manager.restore_package(path) == project()
    import zipfile
    tampered = tmp_path / "tampered.spbackup"
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            payload = source.read(name)
            if name == "project.json":
                payload = payload.replace(b'"QA-1"', b'"TAMPER"')
            target.writestr(name, payload)
    try:
        manager.restore_package(tampered)
    except ValueError as exc:
        assert "checksum" in str(exc) or "invalid" in str(exc)
    else:
        raise AssertionError("tampered backup must be rejected")


def test_audit_records_are_append_only_snapshots():
    trail = AuditTrail()
    after = {"name": "A"}
    record = trail.record("create", "project", "QA-1", after=after)
    after["name"] = "MUTATED"
    assert record["after"]["name"] == "A"
    assert trail.list()[0]["after"]["name"] == "A"
    assert trail.list()[0]["action"] == "create"


def test_workflow_health_has_structured_qc():
    result = project_health(project())
    assert result["ready"] is True
    assert result["qc"]["valid"] is True
    assert "issues" in result["qc"]


def test_priority9_regression_surface_files_exist():
    assert Path(".github/workflows/full-tests.yml").exists()
    assert Path(".github/workflows/drawing-tests.yml").exists()
    assert Path(".github/workflows/tests.yml").exists()
