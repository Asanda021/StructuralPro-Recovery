"""Build and independently restore the synthetic five-storey P5 evidence."""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

from core.platform.application import StructuralProApp
from core.projects.backup import BackupManager
from core.projects.store import ProjectStore
from core.recovery.recovery import backup_database


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_documents(project: dict) -> dict[str, str]:
    found: dict[str, str] = {}

    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
                found[value["path"]] = value["sha256"]
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(project)
    return found


def main() -> int:
    scenario = Path(sys.argv[1]).resolve(strict=True)
    evidence = Path(sys.argv[2]).resolve(strict=True)
    stage = Path(sys.argv[3])
    database = scenario / "prior/engineering/db/projects.db"
    store = ProjectStore(database)
    project = store.get("P")
    revisions = store.revisions("P")
    assert project is not None and len(revisions) == project["_meta"]["version"]
    assert store.integrity_check()["ok"]
    store.close()

    app = StructuralProApp(scenario / "prior/engineering/db")
    current_duration = app.project_schedule("P")["duration"]
    app.store.close()
    documents = source_documents(project)
    assert len(documents) == 4
    for path, expected in documents.items():
        assert sha(Path(path)) == expected

    attachments = {
        f"sources/{index:02d}-{Path(path).name}": path
        for index, path in enumerate(sorted(documents), start=1)
    }
    manager = BackupManager(evidence)
    generated = manager.create_package(project, "P", attachments=attachments)
    package = evidence / "five-storey.spbackup"
    if package.exists():
        raise RuntimeError("evidence package already exists")
    generated.rename(package)
    sqlite_backup = evidence / "five-storey.sqlite"
    backup_database(database, sqlite_backup)

    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    (evidence / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    held = scenario.with_name(scenario.name + "-held")
    scenario.rename(held)
    try:
        assert not database.exists()
        receipt = manager.restore_package_to(
            package,
            stage,
            expected_project_id="P",
            minimum_revision=project["_meta"]["version"],
        )
        restored_project = json.loads((stage / "project.json").read_text(encoding="utf-8"))
        assert restored_project == project
        restored_source_hashes = {
            sha(path) for path in (stage / "sources").iterdir() if path.is_file()
        }
        assert set(documents.values()) <= restored_source_hashes

        restored_store = ProjectStore(sqlite_backup)
        assert restored_store.get("P") == project
        assert len(restored_store.revisions("P")) == len(revisions)
        integrity = restored_store.integrity_check()
        restored_store.close()
    finally:
        held.rename(scenario)

    baseline = project["schedule_baselines"][0]["result"]["duration"]
    progress = [row["actual"] for row in project["progress_reports"]]
    assert (len(project["floors"]), len(project["project_schedule_tasks"])) == (5, 15)
    assert (baseline, current_duration) == (18, 20)
    assert progress == ["12.500000", "45.000000", "75.000000"]
    result = {
        "status": "PASS",
        "synthetic_fixture": True,
        "original_unavailable_during_restore": True,
        "project_id": "P",
        "revision": project["_meta"]["version"],
        "revision_rows": len(revisions),
        "floors": len(project["floors"]),
        "activities": len(project["project_schedule_tasks"]),
        "baseline_days": baseline,
        "current_days": current_duration,
        "progress_actual": progress,
        "boq_rows": len(project["boq"]),
        "resources": len(project["project_resources"]),
        "daily_reports": len(project["project_daily_reports"]),
        "financial_records": len(project["financial_records"]),
        "source_documents": len(documents),
        "restored_files": receipt["files"],
        "sqlite_integrity": integrity,
        "package_sha256": sha(package),
        "sqlite_sha256": sha(sqlite_backup),
        "restored_project_sha256": receipt["sha256"],
    }
    (evidence / "restore-receipt.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
