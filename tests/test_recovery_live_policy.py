"""Current source policy is independent of static historical release contracts."""
import hashlib
import json
from pathlib import Path
import pytest
from scripts import run_quarantined_workflow_qa as qa


def repository(tmp_path):
    root = tmp_path / "source"
    q = root / "recovery/disabled_workflows"
    q.mkdir(parents=True)
    for i in range(193):
        (q / f"w{i:03d}.yml").write_text("permissions: {contents: read}\non: {workflow_dispatch: {}}\n")
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in q.iterdir()}
    (root / "recovery/workflow_sha256.json").write_text(json.dumps(manifest))
    return root


def test_current_real_repository_policy():
    result = qa.current_policy(Path(__file__).resolve().parents[1])
    assert result == {"active_workflows": 0, "verified_quarantined_workflows": 193}


@pytest.mark.parametrize("change", ["permission", "trigger", "extra", "symlink", "parent_symlink", "active"])
def test_current_policy_rejects_unsafe_changes(tmp_path, change):
    root = repository(tmp_path)
    q = root / "recovery/disabled_workflows"
    file = q / "w000.yml"
    if change == "permission": file.write_text("permissions: {contents: write}\n")
    elif change == "trigger": file.write_text("on: {release: {types: [published]}}\n")
    elif change == "extra": (q / "extra.yml").write_text("on: push\n")
    elif change == "symlink":
        file.rename(root / "external.yml"); file.symlink_to(root / "external.yml")
    elif change == "parent_symlink":
        (root / "recovery").rename(root / "external"); (root / "recovery").symlink_to(root / "external", target_is_directory=True)
    else:
        (root / ".github/workflows").mkdir(parents=True)
        (root / ".github/workflows/release.yml").write_text("on: push\n")
    with pytest.raises((RuntimeError, ValueError)):
        qa.current_policy(root)


def test_current_policy_requires_integrity_manifest(tmp_path):
    root = repository(tmp_path)
    (root / "recovery/workflow_sha256.json").unlink()
    with pytest.raises((RuntimeError, ValueError)):
        qa.current_policy(root)
