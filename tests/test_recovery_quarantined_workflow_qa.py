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
    import hashlib, json
    (root / "recovery/workflow_sha256.json").write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / "recovery/disabled_workflows").iterdir()}))
    return root


def test_quarantine_count_guard(tmp_path):
    r = fixture_repo(tmp_path,192)
    with pytest.raises(RuntimeError, match="count"):
        module.workflow_paths(r)


@pytest.mark.parametrize("linked", [False, True])
def test_active_workflows_are_rejected(tmp_path, linked):
    r = fixture_repo(tmp_path)
    (r / ".github").mkdir()
    if linked:
        (r / ".github/workflows").symlink_to(tmp_path / "outside")
    else:
        (r / ".github/workflows").mkdir()
    with pytest.raises(RuntimeError, match="Active"):
        module.workflow_paths(r)
    with pytest.raises(RuntimeError, match="Active"):
        module.current_policy(r)
    d = tmp_path / "disposable"
    d.mkdir()
    with pytest.raises(RuntimeError, match="Active"):
        module.prepare_fixture(r, d)


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


def test_disposable_source_excludes_active_actions_and_git(tmp_path):
    r = fixture_repo(tmp_path)
    import hashlib, json
    files = sorted((r / 'recovery/disabled_workflows').iterdir())
    (r / 'recovery/workflow_sha256.json').write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))
    (r / '.github/workflows').mkdir(parents=True)
    (r / '.github/workflows/acceptance.yml').write_text('name: acceptance\n')
    (r / '.git').write_text('gitdir: /outside/worktree')
    d = tmp_path / 'disposable'
    d.mkdir()
    staged = module.prepare_source(r, d)
    assert not (staged / '.github/workflows').exists()
    assert not (staged / '.git').exists()
    assert module.current_policy(staged)['verified_quarantined_workflows'] == 193
    assert (r / '.github/workflows/acceptance.yml').read_text() == 'name: acceptance\n'
    historical = tmp_path / 'historical'
    historical.mkdir()
    fixture = module.prepare_fixture(staged, historical)
    assert not (fixture / '.git').exists()
    assert not (fixture / '.github/workflows/acceptance.yml').exists()
    assert {p.name: p.read_bytes() for p in (fixture / '.github/workflows').iterdir()} == {p.name: p.read_bytes() for p in files}
    with pytest.raises(RuntimeError, match='Active'):
        module.current_policy(r)


@pytest.mark.parametrize('linked', ['.github', '.github/workflows', 'recovery', 'recovery/disabled_workflows', 'README.md'])
def test_disposable_source_rejects_links(tmp_path, linked):
    r = fixture_repo(tmp_path)
    path = r / linked
    if path.exists():
        import shutil
        if path.is_dir(): shutil.rmtree(path)
        else: path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(tmp_path / 'outside')
    d = tmp_path / 'disposable'
    d.mkdir()
    with pytest.raises(RuntimeError, match='[Ll]ink'):
        module.prepare_source(r, d)


def test_disposable_source_manifest_and_overlap_guards(tmp_path):
    r = fixture_repo(tmp_path)
    (r / 'recovery/workflow_sha256.json').write_text('{}')
    inside = r / 'disposable'
    inside.mkdir()
    with pytest.raises(RuntimeError, match='overlap'):
        module.prepare_source(r, inside)
    d = tmp_path / 'outside'
    d.mkdir()
    with pytest.raises(RuntimeError, match='integrity'):
        module.prepare_source(r, d)


def test_fixture_rejects_tampered_quarantine(tmp_path):
    r = fixture_repo(tmp_path)
    (r / 'recovery/disabled_workflows/w000.yml').write_text('tampered')
    d = tmp_path / 'disposable'
    d.mkdir()
    with pytest.raises(RuntimeError, match='integrity'):
        module.prepare_fixture(r, d)


@pytest.mark.parametrize('mode', ['current', 'historical'])
def test_official_runner_keeps_current_and_historical_results_separate(tmp_path, mode):
    import json
    r = fixture_repo(tmp_path)
    (r / '.github/workflows').mkdir(parents=True)
    (r / '.github/workflows/acceptance.yml').write_text('name: acceptance')
    (r / 'tests').mkdir()
    (r / 'tests/test_current.py').write_text('def test_current(): assert True\n')
    for name in module.HISTORICAL_TESTS:
        (r / name).write_text('def test_historical(): assert False, "historical failure remains visible"\n')
    output = tmp_path / 'result.json'
    status = module.run(r, output=output, mode=mode)
    result = json.loads(output.read_text())
    assert result['source_active_workflows'] == 1
    assert result['source_active_workflows_copied'] == 0
    assert (r / '.github/workflows/acceptance.yml').exists()
    if mode == 'current':
        assert status == 0
        assert result['stats']['passed'] == 1
        assert result['historical_modules_excluded_from_current'] == list(module.HISTORICAL_TESTS)
    else:
        assert status == 1
        assert result['stats']['failed'] == 15
        assert result['overall_green'] is False


def test_junit_reports_every_test_outcome(tmp_path):
    report = tmp_path / 'result.xml'
    report.write_text('<testsuite><testcase classname="first" name="yes"/><testcase classname="second" name="no"><failure message="failed"/></testcase><testcase classname="third" name="later"><skipped/></testcase></testsuite>')
    assert module.junit_summary(report)['results'] == [
        {'name': 'first::yes', 'outcome': 'passed'},
        {'name': 'second::no', 'outcome': 'failed'},
        {'name': 'third::later', 'outcome': 'skipped'},
    ]


def test_official_runner_reports_timeout_without_green(tmp_path):
    import json
    r = fixture_repo(tmp_path)
    (r / 'tests').mkdir()
    (r / 'tests/test_current.py').write_text('import time\ndef test_slow(): time.sleep(2)\n')
    output = tmp_path / 'result.json'
    status = module.run(r, output=output, mode='current', timeout=0.1)
    result = json.loads(output.read_text())
    assert status == 124
    assert result['timed_out'] is True
    assert result['overall_green'] is False
