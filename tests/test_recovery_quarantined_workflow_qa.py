"""Negative-case verification of offline-only historical Actions compatibility."""
from __future__ import annotations
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_quarantined_workflow_qa.py"
spec = importlib.util.spec_from_file_location("historical_workflow_qa", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture_repo(tmp_path, count=193):
    root = tmp_path / "repo"
    (root / "recovery/disabled_workflows").mkdir(parents=True)
    for i in range(count):
        (root / f"recovery/disabled_workflows/w{i:03d}.yml").write_text("name: archived\n",encoding="utf-8")
    (root / "README.md").write_text("source",encoding="utf-8")
    return root


def test_quarantine_count_guard(tmp_path):
    r = fixture_repo(tmp_path,192)
    with pytest.raises(RuntimeError, match="count"):
        module.workflow_paths(r)


def test_active_workflows_are_rejected(tmp_path):
    r = fixture_repo(tmp_path)
    (r / ".github/workflows").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="Active"):
        module.workflow_paths(r)


def test_symlink_in_quarantine_is_rejected(tmp_path):
    r = fixture_repo(tmp_path)
    (r / "recovery/disabled_workflows/sneaky.yml").symlink_to(r / "README.md")
    with pytest.raises(RuntimeError, match="link"):
        module.workflow_paths(r)


def test_prepared_temp_fixture_does_not_change_original(tmp_path):
    r = fixture_repo(tmp_path)
    other = tmp_path / "tmp"
    other.mkdir()
    out = module.prepare_fixture(r,other)
    assert not (r / ".github/workflows").exists()
    assert len(list((out / ".github/workflows").glob("*.yml"))) == 193
    assert (out / "README.md").read_text() == "source"


def test_disallow_disposable_inside_project(tmp_path):
    r = fixture_repo(tmp_path)
    d = r / "temp"
    d.mkdir()
    with pytest.raises(RuntimeError, match="overlap"):
        module.prepare_fixture(r,d)


def test_junit_classifier_handles_success_fail_and_skip(tmp_path):
    p=tmp_path / "results.xml"
    p.write_text('''<testsuite><testcase classname="a" name="ok"/><testcase classname="b" name="bad"><failure message="RuntimeError: arabic_reshaper unavailable">x</failure></testcase><testcase classname="q" name="qt"><failure message="No module named PySide6">x</failure></testcase><testcase classname="z" name="skip"><skipped/></testcase></testsuite>''',encoding="utf-8")
    summary=module.junit_summary(p)
    assert (summary["passed"], summary["failed"], summary["skipped"]) == (1,2,1)
    assert summary["blocked_pdf_dependency"]==1
    assert summary["blocked_pyside6_dependency"]==1
    assert summary["unexpected_failures"]==[]
