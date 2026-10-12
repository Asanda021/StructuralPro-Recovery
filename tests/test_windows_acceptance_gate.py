"""Offline tests for real Windows acceptance infrastructure, no Qt test fakes."""
from pathlib import Path
import importlib.util
import tempfile
import pytest

SPEC=importlib.util.spec_from_file_location("win_gate",Path(__file__).resolve().parents[1]/"scripts/windows_acceptance_gate.py")
mod=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def make_repo(tmp_path):
    q=tmp_path/"recovery"/"disabled_workflows"
    q.mkdir(parents=True)
    for i in range(193):
        (q/f"workflow-{i:03}.yml").write_text("name: test\n",encoding="utf-8")
    return tmp_path


def test_real_recovery_count_and_no_active_workflows(tmp_path):
    repo=make_repo(tmp_path)
    assert mod.active_workflows(repo)==[]
    r,code=mod.perform(repo,repo/"qa",force_platform="linux")
    assert r["quarantined_workflow_count"]==193
    assert code==2
    assert r["status"] in ("BLOCKED_MISSING_DEPENDENCIES","BLOCKED_NOT_WINDOWS")


def test_guard_blocks_new_workflow_without_executing(tmp_path):
    repo=make_repo(tmp_path)
    act=repo/".github/workflows"
    act.mkdir(parents=True)
    (act/"release.yml").write_text("on: push\n",encoding="utf-8")
    r,code=mod.perform(repo,repo/"qa",force_platform="win32")
    assert code==1 and r["status"]=="BLOCKED_UNSAFE_WORKFLOWS"


def test_symlink_directory_is_rejected(tmp_path):
    repo=make_repo(tmp_path)
    dest=repo/"somewhere";dest.mkdir()
    a=repo/".github";a.mkdir();(a/"workflows").symlink_to(dest, target_is_directory=True)
    r,code=mod.perform(repo,repo/"qa")
    assert code==1 and r["status"]=="FAILED_PRECHECK"


def test_wrong_workflow_count_fails_closed(tmp_path):
    repo=make_repo(tmp_path)
    (repo/"recovery/disabled_workflows/workflow-000.yml").unlink()
    r,code=mod.perform(repo,repo/"qa")
    assert code==1 and r["status"]=="BLOCKED_INCOMPLETE_RECOVERY"


def test_missing_dependencies_is_reported_without_gui(tmp_path,monkeypatch):
    repo=make_repo(tmp_path)
    monkeypatch.setattr(mod,"missing_dependencies",lambda:["PySide6"])
    r,code=mod.perform(repo,repo/"qa",force_platform="win32")
    assert code==2 and r["status"]=="BLOCKED_MISSING_DEPENDENCIES"
    assert r["missing_dependencies"]==["PySide6"]


def test_not_windows_is_blocked_after_complete_dependency_preflight(tmp_path,monkeypatch):
    repo=make_repo(tmp_path)
    monkeypatch.setattr(mod,"missing_dependencies",lambda:[])
    r,code=mod.perform(repo,repo/"qa",force_platform="linux")
    assert code==2 and r["status"]=="BLOCKED_NOT_WINDOWS"


def test_no_fake_green_on_non_windows_when_requested_preflight(tmp_path,monkeypatch):
    repo=make_repo(tmp_path)
    monkeypatch.setattr(mod,"missing_dependencies",lambda:[])
    r,code=mod.perform(repo,repo/"qa",force_platform="linux",preflight_only=True)
    assert code==2 and "PASSED" not in r["status"]


@pytest.mark.parametrize("linked_directory", [False, True])
def test_quarantined_symlinks_fail_before_dependency_preflight(tmp_path, monkeypatch, linked_directory):
    repo = make_repo(tmp_path)
    quarantine = repo / "recovery/disabled_workflows"
    if linked_directory:
        moved = repo / "external-workflows"
        quarantine.rename(moved)
        quarantine.symlink_to(moved, target_is_directory=True)
    else:
        source = quarantine / "workflow-000.yml"
        external = repo / "external.yml"
        source.rename(external)
        source.symlink_to(external)
    monkeypatch.setattr(mod, "missing_dependencies", lambda: [])
    report, code = mod.perform(repo, repo / "qa", force_platform="linux")
    assert code == 1
    assert report["status"] == "FAILED_PRECHECK"
    assert "linked" in report["reason"] or "symbolic link" in report["reason"]


def test_quarantine_rejects_unexpected_files(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    (repo / "recovery/disabled_workflows/unexpected.txt").write_text("unexpected")
    monkeypatch.setattr(mod, "missing_dependencies", lambda: [])
    report, code = mod.perform(repo, repo / "qa", force_platform="linux")
    assert code == 1 and report["status"] == "FAILED_PRECHECK"
